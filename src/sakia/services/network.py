from sakia.data.connectors import NodeConnector
from sakia.data.entities import Node
from sakia.errors import InvalidNodeCurrency
from sakia.tools.decorators import asyncify
import logging
import time
import asyncio
from duniterpy.key import VerifyingKey
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from collections import Counter


class NetworkService(QObject):
    """
    A network is managing nodes polling and crawling of a
    given community.
    """
    nodes_changed = pyqtSignal()
    root_nodes_changed = pyqtSignal()

    def __init__(self, currency, processor, connectors, session):
        """
        Constructor of a network

        :param str currency: The currency name of the community
        :param sakia.data.processors.NodesProcessor processor: the nodes processor for given currency
        :param list connectors: The connectors to nodes of the network
        :param aiohttp.ClientSession session: The main aiohttp client session
        """
        super().__init__()
        self._processor = processor
        self._connectors = []
        for c in connectors:
            self.add_connector(c)
        self.currency = currency
        self._must_crawl = False
        self._block_found = self._processor.current_buid()
        self._client_session = session
        self._discovery_stack = []

    @classmethod
    def create(cls, processor, node_connector):
        """
        Create a new network with one knew node
        Crawls the nodes from the first node to build the
        community network

        :param sakia.data.processors.NodeProcessor processor: The nodes processor
        :param sakia.data.connectors.NodeConnector node_connector: The first connector of the network service
        :return:
        """
        connectors = [node_connector]
        processor.insert_node(node_connector.node)
        network = cls(node_connector.node.currency, processor, connectors, node_connector.session)
        return network

    def start_coroutines(self):
        """
        Start network nodes crawling
        :return:
        """
        asyncio.ensure_future(self.discover_network())

    async def stop_coroutines(self, closing=False):
        """
        Stop network nodes crawling.
        """
        self._must_crawl = False
        close_tasks = []
        logging.debug("Start closing")
        for connector in self._connectors:
            close_tasks.append(asyncio.ensure_future(connector.close_ws()))
        logging.debug("Closing {0} websockets".format(len(close_tasks)))
        if len(close_tasks) > 0:
            await asyncio.wait(close_tasks, timeout=15)
        if closing:
            logging.debug("Closing client session")
            await self._client_session.close()
        logging.debug("Closed")

    @property
    def session(self):
        return self._client_session

    def continue_crawling(self):
        return self._must_crawl

    def _check_nodes_sync(self):
        """
        Check nodes sync with the following rules :
        1 : The block of the majority
        2 : The more last different issuers
        3 : The more difficulty
        4 : The biggest number or timestamp
        """
        online_nodes = self._processor.online_nodes()
        # rule number 1 : block of the majority
        blocks = [n.current_buid.sha_hash for n in online_nodes if n.current_buid.sha_hash]
        blocks_occurences = Counter(blocks)
        blocks_by_occurences = {}
        for key, value in blocks_occurences.items():
            the_block = [n.current_buid.sha_hash
                         for n in online_nodes if n.current_buid.sha_hash == key][0]
            if value not in blocks_by_occurences:
                blocks_by_occurences[value] = [the_block]
            else:
                blocks_by_occurences[value].append(the_block)

        if len(blocks_by_occurences) == 0:
            for n in [n for n in online_nodes if n.state in (Node.ONLINE, Node.DESYNCED)]:
                n.state = Node.ONLINE
                self._processor.update_node(n)
            return

        most_present = max(blocks_by_occurences.keys())

        synced_block_hash = blocks_by_occurences[most_present][0]

        for n in online_nodes:
            if n.current_buid.sha_hash == synced_block_hash:
                n.state = Node.ONLINE
            else:
                n.state = Node.DESYNCED
            self._processor.update_node(n)

    def add_connector(self, node_connector):
        """
        Add a nod to the network.
        """
        self._connectors.append(node_connector)
        node_connector.changed.connect(self.handle_change)
        node_connector.error.connect(self.handle_error)
        node_connector.identity_changed.connect(self.handle_identity_change)
        node_connector.neighbour_found.connect(self.handle_new_node)
        logging.debug("{:} connected".format(node_connector.node.pubkey[:5]))

    @asyncify
    async def refresh_once(self):
        for connector in self._connectors:
            await asyncio.sleep(1)
            connector.refresh(manual=True)

    async def discover_network(self):
        """
        Start crawling which never stops.
        To stop this crawling, call "stop_crawling" method.
        """
        self._must_crawl = True
        first_loop = True
        asyncio.ensure_future(self.discovery_loop())
        while self.continue_crawling():
            for connector in self._connectors:
                if self.continue_crawling():
                    connector.refresh()
                    if not first_loop:
                        await asyncio.sleep(15)
            first_loop = False
            await asyncio.sleep(15)

        logging.debug("End of network discovery")

    async def discovery_loop(self):
        """
        Handle poping of nodes in discovery stack
        :return:
        """
        while self.continue_crawling():
            try:
                await asyncio.sleep(1)
                peer = self._discovery_stack.pop()
                if self._processor.unknown_node(peer.pubkey):
                    logging.debug("New node found : {0}".format(peer.pubkey[:5]))
                    try:
                        connector = NodeConnector.from_peer(self.currency, peer, self.session)
                        self._processor.insert_node(connector.node)
                        connector.refresh(manual=True)
                        self.add_connector(connector)
                        self.nodes_changed.emit()
                    except InvalidNodeCurrency as e:
                        logging.debug(str(e))
                else:
                    self._processor.update_peer(peer)
            except IndexError:
                await asyncio.sleep(2)

    def handle_new_node(self, peer):
        key = VerifyingKey(peer.pubkey)
        if key.verify_document(peer):
            if len(self._discovery_stack) < 1000 \
            and peer.signatures[0] not in [p.signatures[0] for p in self._discovery_stack]:
                logging.debug("Stacking new peer document : {0}".format(peer.pubkey))
                self._discovery_stack.append(peer)
        else:
            logging.debug("Wrong document received : {0}".format(peer.signed_raw()))

    @pyqtSlot()
    def handle_identity_change(self):
        connector = self.sender()
        self._processor.update_node(connector.node)
        self.nodes_changed.emit()

    @pyqtSlot()
    def handle_error(self):
        node = self.sender()
        if node.state in (Node.OFFLINE, Node.CORRUPTED) and \
                                node.last_change + 3600 < time.time():
            node.disconnect()
            self.nodes.remove(node)
            self.nodes_changed.emit()

    @pyqtSlot()
    def handle_change(self):
        node_connector = self.sender()

        if node_connector.node.state in (Node.ONLINE, Node.DESYNCED):
            self._check_nodes_sync()
        self.nodes_changed.emit()
        self._processor.update_node(node_connector.node)

        if node_connector.node.state == Node.ONLINE:
            current_buid = self._processor.current_buid()
            logging.debug("{0} -> {1}".format(self._block_found.sha_hash[:10], current_buid.sha_hash[:10]))
            if self._block_found.sha_hash != current_buid.sha_hash:
                logging.debug("Latest block changed : {0}".format(current_buid.number))
                # If new latest block is lower than the previously found one
                # or if the previously found block is different locally
                # than in the main chain, we declare a rollback
                if current_buid <= self._block_found \
                   or node_connector.node.previous_buid != self._block_found:
                    self._block_found = current_buid
                    self.blockchain_rollback.emit(current_buid.number)
                else:
                    self._block_found = current_buid
                    self.blockchain_progress.emit(current_buid.number)
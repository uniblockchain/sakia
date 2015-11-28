import sys
import unittest
import asyncio
import quamash
import time
import logging
from ucoinpy.documents.peer import BMAEndpoint as PyBMAEndpoint
from PyQt5.QtCore import QLocale, Qt
from cutecoin.tests.mocks.bma import nice_blockchain
from cutecoin.core.registry.identities import IdentitiesRegistry
from cutecoin.core.app import Application
from cutecoin.core import Account, Community, Wallet
from cutecoin.core.net import Network, Node
from cutecoin.core.net.api.bma.access import BmaAccess
from cutecoin.tests import QuamashTest
from ucoinpy.documents.peer import BMAEndpoint


class TestTxHistory(unittest.TestCase, QuamashTest):
    def setUp(self):
        self.setUpQuamash()
        QLocale.setDefault(QLocale("en_GB"))
        self.identities_registry = IdentitiesRegistry({})

        self.application = Application(self.qapplication, self.lp, self.identities_registry)
        self.application.preferences['notifications'] = False

        self.endpoint = BMAEndpoint(PyBMAEndpoint("", "127.0.0.1", "", 50000))
        self.node = Node("test_currency", [self.endpoint],
                         "", "HnFcSms8jzwngtVomTTnzudZx7SHUQY8sVE1y8yBmULk",
                         nice_blockchain.bma_blockchain_current, Node.ONLINE,
                         time.time(), {}, "ucoin", "0.14.0", 0)
        self.network = Network.create(self.node)
        self.bma_access = BmaAccess.create(self.network)
        self.community = Community("test_currency", self.network, self.bma_access)

        self.wallet = Wallet(0, "7Aqw6Efa9EzE7gtsc8SveLLrM7gm6NEGoywSv4FJx6pZ",
                             "Wallet 1", self.identities_registry)
        self.wallet.init_cache(self.application, self.community)

        # Salt/password : "testcutecoin/testcutecoin"
        # Pubkey : 7Aqw6Efa9EzE7gtsc8SveLLrM7gm6NEGoywSv4FJx6pZ
        self.account = Account("testcutecoin", "7Aqw6Efa9EzE7gtsc8SveLLrM7gm6NEGoywSv4FJx6pZ",
                               "john", [self.community], [self.wallet], [], self.identities_registry)

    def tearDown(self):
        self.tearDownQuamash()

    # this test fails with old algorithm
    def notest_txhistory_reload(self):
        mock = nice_blockchain.get_mock()
        time.sleep(2)
        logging.debug(mock.pretend_url)

        received_list = []
        self.lp.run_until_complete(self.wallet.caches[self.community.currency].
                                   refresh(self.community, received_list))
        self.assertEquals(len(received_list), 2)
        received_value = sum([r.metadata['amount'] for r in received_list])
        self.assertEqual(received_value, 60)
        self.assertEqual(len(self.wallet.dividends(self.community)), 2)
        dividends_value = sum([ud['amount'] for ud in self.wallet.dividends(self.community)])
        self.assertEqual(dividends_value, 15)
        mock.delete_mock()

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()

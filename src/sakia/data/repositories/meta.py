import attr
import os
import logging
import sqlite3
from duniterpy.documents import BlockUID
from .connections import ConnectionsRepo
from .identities import IdentitiesRepo
from .blockchains import BlockchainsRepo
from .certifications import CertificationsRepo
from .transactions import TransactionsRepo
from .dividends import DividendsRepo
from .nodes import NodesRepo
from .sources import SourcesRepo
from .contacts import ContactsRepo


@attr.s(frozen=True)
class SakiaDatabase:
    """
    This is Sakia unique SQLite database.
    """
    conn = attr.ib()  # :type sqlite3.Connection
    connections_repo = attr.ib(default=None)
    identities_repo = attr.ib(default=None)
    blockchains_repo = attr.ib(default=None)
    certifications_repo = attr.ib(default=None)
    transactions_repo = attr.ib(default=None)
    nodes_repo = attr.ib(default=None)
    sources_repo = attr.ib(default=None)
    dividends_repo = attr.ib(default=None)
    contacts_repo = attr.ib(default=None)
    _logger = attr.ib(default=attr.Factory(lambda: logging.getLogger('sakia')))

    @classmethod
    def load_or_init(cls, options, profile_name):
        sqlite3.register_adapter(BlockUID, str)
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))
        db_path = os.path.join(options.config_path, profile_name, options.currency + ".db")
        con = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        meta = SakiaDatabase(con, ConnectionsRepo(con), IdentitiesRepo(con),
                             BlockchainsRepo(con), CertificationsRepo(con), TransactionsRepo(con),
                             NodesRepo(con), SourcesRepo(con), DividendsRepo(con), ContactsRepo(con))

        meta.prepare()
        meta.upgrade_database()
        return meta

    def prepare(self):
        """
        Prepares the database if the table is missing
        """
        with self.conn:
            self._logger.debug("Initializing meta database")
            self.conn.execute("PRAGMA busy_timeout = 50000")
            self.conn.execute("""CREATE TABLE IF NOT EXISTS meta(
                               id INTEGER NOT NULL,
                               version INTEGER NOT NULL,
                               PRIMARY KEY (id)
                               )"""
                              )

    @property
    def upgrades(self):
        return [
            self.create_all_tables,
            self.add_ud_rythm_parameters,
            self.add_contacts,
            self.add_sentry_property
        ]

    def upgrade_database(self, to=0):
        """
        Execute the migrations
        """
        self._logger.debug("Begin upgrade of database...")
        version = self.version()
        nb_versions = to if to else len(self.upgrades)
        for v in range(version, nb_versions):
            self._logger.debug("Upgrading to version {0}...".format(v))
            self.upgrades[v]()
            with self.conn:
                self.conn.execute("UPDATE meta SET version=? WHERE id=1", (version + 1,))
            version += 1
        self._logger.debug("End upgrade of database...")

    def create_all_tables(self):
        """
        Init all the tables
        :return:
        """
        self._logger.debug("Initialiazing all databases")
        sql_file = open(os.path.join(os.path.dirname(__file__), 'meta.sql'), 'r')
        with self.conn:
            self.conn.executescript(sql_file.read())

    def add_ud_rythm_parameters(self):
        """
        Init all the tables
        :return:
        """
        self._logger.debug("Add ud rythm parameters to blockchains table")
        sql_file = open(os.path.join(os.path.dirname(__file__), '000_add_ud_rythm_parameters.sql'), 'r')
        with self.conn:
            self.conn.executescript(sql_file.read())

    def add_contacts(self):
        """
        Init all the tables
        :return:
        """
        self._logger.debug("Add contacts table")
        sql_file = open(os.path.join(os.path.dirname(__file__), '001_add_contacts.sql'), 'r')
        with self.conn:
            self.conn.executescript(sql_file.read())

    def add_sentry_property(self):
        """
        Init all the tables
        :return:
        """
        self._logger.debug("Add sentry property")
        sql_file = open(os.path.join(os.path.dirname(__file__), '002_add_sentry_property.sql'), 'r')
        with self.conn:
            self.conn.executescript(sql_file.read())

    def version(self):
        with self.conn:
            c = self.conn.execute("SELECT * FROM meta WHERE id=1")
            data = c.fetchone()
            if data:
                return data[1]
            else:
                self.conn.execute("INSERT INTO meta VALUES (1, 0)")
                return 0

    def commit(self):
        self.conn.commit()

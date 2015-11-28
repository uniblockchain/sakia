import sys
import unittest
import asyncio
import quamash
import logging
from PyQt5.QtCore import QLocale
from cutecoin.core.registry.identities import IdentitiesRegistry
from cutecoin.core import Wallet
from cutecoin.tests import QuamashTest


class TestWallet(unittest.TestCase, QuamashTest):
    def setUp(self):
        self.setUpQuamash()
        QLocale.setDefault(QLocale("en_GB"))
        self.identities_registry = IdentitiesRegistry({})

    def tearDown(self):
        self.tearDownQuamash()

    def test_load_save_wallet(self):
        wallet = Wallet(0, "7Aqw6Efa9EzE7gtsc8SveLLrM7gm6NEGoywSv4FJx6pZ",
                             "Wallet 1", self.identities_registry)

        json_data = wallet.jsonify()
        wallet_from_json = Wallet.load(json_data, self.identities_registry)
        self.assertEqual(wallet.walletid, wallet_from_json.walletid)
        self.assertEqual(wallet.pubkey, wallet_from_json.pubkey)
        self.assertEqual(wallet.name, wallet_from_json.name)
        self.assertEqual(wallet._identities_registry, wallet_from_json._identities_registry)

if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()

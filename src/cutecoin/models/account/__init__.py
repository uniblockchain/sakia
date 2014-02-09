'''
Created on 1 févr. 2014

@author: inso
'''

import ucoinpy as ucoin
import gnupg
import logging
from cutecoin.models.account.wallets import Wallets

class Account(object):
    '''
    classdocs
    '''

    def __init__(self, gpgKey, name, communities):
        '''
        Constructor
        '''
        self.gpgKey = gpgKey
        self.name = name
        self.communities = communities
        self.wallets = Wallets()
        for community in self.communities.communitiesList:
            wallet = self.wallets.addWallet(community.currency)
            wallet.refreshCoins(community, self.keyFingerprint())

        self.receivedTransactions = []
        self.sentTransactions = []

    def addWallet(name, currency):
        self.wallets.addWallet(name, currency)

    def keyFingerprint(self):
        gpg = gnupg.GPG()
        availableKeys = gpg.list_keys()
        logging.debug(self.gpgKey)
        for k in availableKeys:
            logging.debug(k)
            if k['keyid'] == self.gpgKey:
                return k['fingerprint']
        return ""

    def transactionsReceived(self):
        pass

    def transactionsSent(self):
        pass




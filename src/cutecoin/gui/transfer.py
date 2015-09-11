"""
Created on 2 févr. 2014

@author: inso
"""
from PyQt5.QtWidgets import QDialog, QMessageBox, QApplication
from PyQt5.QtCore import QRegExp, Qt, QLocale, pyqtSlot
from PyQt5.QtGui import QRegExpValidator

from ..gen_resources.transfer_uic import Ui_TransferMoneyDialog
from . import toast
from ..tools.decorators import asyncify
import asyncio


class TransferMoneyDialog(QDialog, Ui_TransferMoneyDialog):

    """
    classdocs
    """

    def __init__(self, app, sender, password_asker):
        """
        Constructor
        :param cutecoin.core.Application app: The application
        :param cutecoin.core.Account sender: The sender
        :param cutecoin.gui.password_asker.Password_Asker password_asker: The password asker
        :return:
        """
        super().__init__()
        self.setupUi(self)
        self.app = app
        self.account = sender
        self.password_asker = password_asker
        self.recipient_trusts = []
        self.wallet = None
        self.community = self.account.communities[0]
        self.wallet = self.account.wallets[0]

        regexp = QRegExp('^([ a-zA-Z0-9-_:/;*?\[\]\(\)\\\?!^+=@&~#{}|<>%.]{0,255})$')
        validator = QRegExpValidator(regexp)
        self.edit_message.setValidator(validator)

        for community in self.account.communities:
            self.combo_community.addItem(community.currency)

        for wallet in self.account.wallets:
            self.combo_wallets.addItem(wallet.name)

        for contact in sender.contacts:
            self.combo_contact.addItem(contact['name'])

        if len(self.account.contacts) == 0:
            self.combo_contact.setEnabled(False)
            self.radio_contact.setEnabled(False)
            self.radio_pubkey.setChecked(True)

    def accept(self):
        comment = self.edit_message.text()

        if self.radio_contact.isChecked():
            index = self.combo_contact.currentIndex()
            recipient = self.account.contacts[index]['pubkey']
        else:
            recipient = self.edit_pubkey.text()
        amount = self.spinbox_amount.value()

        if not amount:
            QMessageBox.critical(self, self.tr("Money transfer"),
                                 self.tr("No amount. Please give the transfert amount"),
                                 QMessageBox.Ok)
            return

        password = self.password_asker.exec_()
        if self.password_asker.result() == QDialog.Rejected:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        self.wallet.transfer_broadcasted.connect(self.money_sent)
        self.wallet.broadcast_error.connect(self.handle_error)
        asyncio.async(self.wallet.send_money(self.account.salt, password, self.community,
                                   recipient, amount, comment))

    @pyqtSlot(str)
    def money_sent(self, receiver_uid):
        if self.app.preferences['notifications']:
            toast.display(self.tr("Transfer"),
                      self.tr("Success sending money to {0}").format(receiver_uid))
        else:
            QMessageBox.information(self, self.tr("Transfer"),
                      self.tr("Success sending money to {0}").format(receiver_uid))
        self.wallet.transfer_broadcasted.disconnect()
        self.wallet.broadcast_error.disconnect(self.handle_error)
        QApplication.restoreOverrideCursor()
        super().accept()

    @pyqtSlot(int, str)
    def handle_error(self, error_code, text):
        if self.app.preferences['notifications']:
            toast.display(self.tr("Error"), self.tr("{0} : {1}".format(error_code, text)))
        else:
            QMessageBox.critical(self, self.tr("Error"), self.tr("{0} : {1}".format(error_code, text)))
        self.wallet.transfer_broadcasted.disconnect()
        self.wallet.broadcast_error.disconnect(self.handle_error)
        QApplication.restoreOverrideCursor()

    @asyncify
    @asyncio.coroutine
    def amount_changed(self):
        dividend = yield from self.community.dividend()
        amount = self.spinbox_amount.value()
        relative = amount / dividend
        self.spinbox_relative.blockSignals(True)
        self.spinbox_relative.setValue(relative)
        self.spinbox_relative.blockSignals(False)

    @asyncify
    @asyncio.coroutine
    def relative_amount_changed(self):
        dividend = yield from self.community.dividend()
        relative = self.spinbox_relative.value()
        amount = relative * dividend
        self.spinbox_amount.blockSignals(True)
        self.spinbox_amount.setValue(amount)
        self.spinbox_amount.blockSignals(False)

    @asyncify
    @asyncio.coroutine
    def change_current_community(self, index):
        self.community = self.account.communities[index]
        amount = yield from self.wallet.value(self.community)

        ref_text = yield from self.account.current_ref(amount, self.community, self.app)\
            .diff_localized(units=True,
                            international_system=self.app.preferences['international_system_of_units'])
        self.label_total.setText("{0}".format(ref_text))
        self.spinbox_amount.setSuffix(" " + self.community.currency)
        self.spinbox_amount.setValue(0)
        amount = yield from self.wallet.value(self.community)
        dividend = yield from self.community.dividend()
        relative = amount / dividend
        self.spinbox_amount.setMaximum(amount)
        self.spinbox_relative.setMaximum(relative)

    @asyncify
    @asyncio.coroutine
    def change_displayed_wallet(self, index):
        self.wallet = self.account.wallets[index]
        amount = yield from self.wallet.value(self.community)
        ref_text = yield from self.account.current_ref(amount, self.community, self.app)\
            .diff_localized(units=True,
                            international_system=self.app.preferences['international_system_of_units'])
        self.label_total.setText("{0}".format(ref_text))
        self.spinbox_amount.setValue(0)
        amount = yield from self.wallet.value(self.community)
        dividend = yield from self.community.dividend()
        relative = amount / dividend
        self.spinbox_amount.setMaximum(amount)
        self.spinbox_relative.setMaximum(relative)

    def recipient_mode_changed(self, pubkey_toggled):
        self.edit_pubkey.setEnabled(pubkey_toggled)
        self.combo_contact.setEnabled(not pubkey_toggled)

    def async_exec(self):
        future = asyncio.Future()
        self.finished.connect(lambda r: future.set_result(r))
        self.open()
        return future

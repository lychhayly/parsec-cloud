# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'forms/register_device.ui'
#
# Created by: PyQt5 UI code generator 5.11.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_RegisterDevice(object):
    def setupUi(self, RegisterDevice):
        RegisterDevice.setObjectName("RegisterDevice")
        RegisterDevice.setWindowModality(QtCore.Qt.ApplicationModal)
        RegisterDevice.resize(463, 403)
        RegisterDevice.setModal(True)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(RegisterDevice)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.device_name = QtWidgets.QLineEdit(RegisterDevice)
        self.device_name.setObjectName("device_name")
        self.horizontalLayout_2.addWidget(self.device_name)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.password = QtWidgets.QLineEdit(RegisterDevice)
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setObjectName("password")
        self.horizontalLayout.addWidget(self.password)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.check_box_use_nitrokey = QtWidgets.QCheckBox(RegisterDevice)
        self.check_box_use_nitrokey.setObjectName("check_box_use_nitrokey")
        self.verticalLayout.addWidget(self.check_box_use_nitrokey)
        self.widget_nitrokey = QtWidgets.QWidget(RegisterDevice)
        self.widget_nitrokey.setObjectName("widget_nitrokey")
        self.formLayout = QtWidgets.QFormLayout(self.widget_nitrokey)
        self.formLayout.setObjectName("formLayout")
        self.label_2 = QtWidgets.QLabel(self.widget_nitrokey)
        self.label_2.setObjectName("label_2")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_2)
        self.label_3 = QtWidgets.QLabel(self.widget_nitrokey)
        self.label_3.setObjectName("label_3")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.label_4 = QtWidgets.QLabel(self.widget_nitrokey)
        self.label_4.setObjectName("label_4")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_4)
        self.combo_nitrokey_token = QtWidgets.QComboBox(self.widget_nitrokey)
        self.combo_nitrokey_token.setObjectName("combo_nitrokey_token")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.combo_nitrokey_token)
        self.combo_nitrokey_key = QtWidgets.QComboBox(self.widget_nitrokey)
        self.combo_nitrokey_key.setObjectName("combo_nitrokey_key")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.combo_nitrokey_key)
        self.line_edit_nitrokey_pin = QtWidgets.QLineEdit(self.widget_nitrokey)
        self.line_edit_nitrokey_pin.setObjectName("line_edit_nitrokey_pin")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.line_edit_nitrokey_pin)
        self.verticalLayout.addWidget(self.widget_nitrokey)
        self.outcome_panel = QtWidgets.QWidget(RegisterDevice)
        self.outcome_panel.setObjectName("outcome_panel")
        self.outcome_panel_layout = QtWidgets.QHBoxLayout(self.outcome_panel)
        self.outcome_panel_layout.setObjectName("outcome_panel_layout")
        self.outcome_status = QtWidgets.QLabel(self.outcome_panel)
        self.outcome_status.setText("")
        self.outcome_status.setWordWrap(True)
        self.outcome_status.setObjectName("outcome_status")
        self.outcome_panel_layout.addWidget(self.outcome_status)
        self.verticalLayout.addWidget(self.outcome_panel)
        self.config_waiter_panel = QtWidgets.QWidget(RegisterDevice)
        self.config_waiter_panel.setObjectName("config_waiter_panel")
        self.config_waiter_panel_layout = QtWidgets.QVBoxLayout(self.config_waiter_panel)
        self.config_waiter_panel_layout.setObjectName("config_waiter_panel_layout")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label = QtWidgets.QLabel(self.config_waiter_panel)
        self.label.setObjectName("label")
        self.horizontalLayout_4.addWidget(self.label)
        self.device_token = QtWidgets.QLineEdit(self.config_waiter_panel)
        self.device_token.setReadOnly(True)
        self.device_token.setObjectName("device_token")
        self.horizontalLayout_4.addWidget(self.device_token)
        self.config_waiter_panel_layout.addLayout(self.horizontalLayout_4)
        self.config_waiter_label = QtWidgets.QLabel(self.config_waiter_panel)
        self.config_waiter_label.setWordWrap(True)
        self.config_waiter_label.setObjectName("config_waiter_label")
        self.config_waiter_panel_layout.addWidget(self.config_waiter_label)
        self.verticalLayout.addWidget(self.config_waiter_panel)
        self.verticalLayout_2.addLayout(self.verticalLayout)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        spacerItem = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
        )
        self.horizontalLayout_3.addItem(spacerItem)
        self.button_register_device = QtWidgets.QPushButton(RegisterDevice)
        self.button_register_device.setObjectName("button_register_device")
        self.horizontalLayout_3.addWidget(self.button_register_device)
        self.verticalLayout_2.addLayout(self.horizontalLayout_3)
        self.button_box = QtWidgets.QDialogButtonBox(RegisterDevice)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        self.button_box.setCenterButtons(True)
        self.button_box.setObjectName("button_box")
        self.verticalLayout_2.addWidget(self.button_box)
        spacerItem1 = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.verticalLayout_2.addItem(spacerItem1)

        self.retranslateUi(RegisterDevice)
        self.check_box_use_nitrokey.toggled["bool"].connect(self.widget_nitrokey.setVisible)
        self.check_box_use_nitrokey.toggled["bool"].connect(self.password.setDisabled)
        self.button_box.accepted.connect(RegisterDevice.accept)
        self.button_box.rejected.connect(RegisterDevice.reject)
        QtCore.QMetaObject.connectSlotsByName(RegisterDevice)

    def retranslateUi(self, RegisterDevice):
        _translate = QtCore.QCoreApplication.translate
        RegisterDevice.setWindowTitle(_translate("RegisterDevice", "Register new device"))
        self.device_name.setPlaceholderText(_translate("RegisterDevice", "Device name"))
        self.password.setPlaceholderText(_translate("RegisterDevice", "Password"))
        self.check_box_use_nitrokey.setText(
            _translate("RegisterDevice", "Use NitroKey authentication instead of password")
        )
        self.label_2.setText(_translate("RegisterDevice", "NitroKey PIN"))
        self.label_3.setText(_translate("RegisterDevice", "Token ID"))
        self.label_4.setText(_translate("RegisterDevice", "Key ID"))
        self.label.setText(_translate("RegisterDevice", "Device's token"))
        self.device_token.setPlaceholderText(_translate("RegisterDevice", "Token"))
        self.config_waiter_label.setText(
            _translate("RegisterDevice", "Waiting for the new device...")
        )
        self.button_register_device.setText(_translate("RegisterDevice", "OK"))

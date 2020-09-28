# Parsec Cloud (https://parsec.cloud) Copyright (c) AGPLv3 2019 Scille SAS

import pytest
from PyQt5 import QtCore

from parsec.core.local_device import save_device_with_password, list_available_devices
from parsec.core.gui.parsec_application import ParsecApp
from parsec.core.gui.login_widget import (
    LoginPasswordInputWidget,
    LoginAccountsWidget,
    LoginNoDevicesWidget,
)


@pytest.mark.gui
@pytest.mark.trio
async def test_login(aqtbot, gui_factory, autoclose_dialog, core_config, alice):
    # Create an existing device before starting the gui
    password = "P@ssw0rd"
    save_device_with_password(core_config.config_dir, alice, password)

    gui = await gui_factory()
    lw = gui.test_get_login_widget()
    tabw = gui.test_get_tab()

    accounts_w = lw.widget.layout().itemAt(0).widget()
    assert accounts_w

    # Only one device, we skip the device selection

    def _password_widget_shown():
        assert isinstance(lw.widget.layout().itemAt(0).widget(), LoginPasswordInputWidget)

    await aqtbot.wait_until(_password_widget_shown)

    password_w = lw.widget.layout().itemAt(0).widget()

    await aqtbot.key_clicks(password_w.line_edit_password, "P@ssw0rd")

    async with aqtbot.wait_signals([lw.login_with_password_clicked, tabw.logged_in]):
        await aqtbot.mouse_click(password_w.button_login, QtCore.Qt.LeftButton)

    central_widget = gui.test_get_central_widget()
    assert central_widget is not None
    assert (
        central_widget.button_user.text() == f"{alice.organization_id}\n{alice.short_user_display}"
    )
    assert (
        gui.tab_center.tabText(0)
        == f"{alice.organization_id} - {alice.short_user_display} - {alice.device_display}"
    )


@pytest.mark.gui
@pytest.mark.trio
async def test_login_back_to_account_list(
    aqtbot, gui_factory, autoclose_dialog, core_config, alice, bob
):
    # Create an existing device before starting the gui
    password = "P@ssw0rd"
    save_device_with_password(core_config.config_dir, alice, password)
    save_device_with_password(core_config.config_dir, bob, password)

    gui = await gui_factory()
    lw = gui.test_get_login_widget()

    accounts_w = lw.widget.layout().itemAt(0).widget()
    assert accounts_w

    async with aqtbot.wait_signal(accounts_w.account_clicked):
        await aqtbot.mouse_click(
            accounts_w.accounts_widget.layout().itemAt(0).widget(), QtCore.Qt.LeftButton
        )

    def _password_widget_shown():
        assert isinstance(lw.widget.layout().itemAt(0).widget(), LoginPasswordInputWidget)

    await aqtbot.wait_until(_password_widget_shown)

    password_w = lw.widget.layout().itemAt(0).widget()

    async with aqtbot.wait_signal(password_w.back_clicked):
        await aqtbot.mouse_click(password_w.button_back, QtCore.Qt.LeftButton)

    def _account_widget_shown():
        assert isinstance(lw.widget.layout().itemAt(0).widget(), LoginAccountsWidget)


@pytest.mark.gui
@pytest.mark.trio
async def test_login_no_devices(aqtbot, gui_factory, autoclose_dialog):
    gui = await gui_factory()
    lw = gui.test_get_login_widget()

    no_device_w = lw.widget.layout().itemAt(0).widget()
    assert isinstance(no_device_w, LoginNoDevicesWidget)


@pytest.mark.gui
@pytest.mark.trio
async def test_login_device_list(aqtbot, gui_factory, autoclose_dialog, core_config, alice, bob):
    password = "P@ssw0rd"
    save_device_with_password(core_config.config_dir, alice, password)
    save_device_with_password(core_config.config_dir, bob, password)

    gui = await gui_factory()
    lw = gui.test_get_login_widget()

    accounts_w = lw.widget.layout().itemAt(0).widget()
    assert accounts_w

    assert accounts_w.accounts_widget.layout().count() == 3
    acc1_w = accounts_w.accounts_widget.layout().itemAt(0).widget()
    acc2_w = accounts_w.accounts_widget.layout().itemAt(1).widget()

    assert acc1_w.label_name.text() in ["Alicey McAliceFace", "Boby McBobFace"]
    assert acc2_w.label_name.text() in ["Alicey McAliceFace", "Boby McBobFace"]

    assert acc1_w.label_device.text() == "My dev1 machine"
    assert acc1_w.label_organization.text() == "CoolOrg"
    assert acc2_w.label_device.text() == "My dev1 machine"
    assert acc2_w.label_organization.text() == "CoolOrg"


@pytest.mark.gui
@pytest.mark.trio
async def test_login_no_available_devices(
    aqtbot, gui_factory, autoclose_dialog, core_config, alice, qt_thread_gateway
):
    password = "P@ssw0rd"
    save_device_with_password(core_config.config_dir, alice, password)

    device = list_available_devices(core_config.config_dir)[0]

    gui = await gui_factory()

    ParsecApp.add_connected_device(device.organization_id, device.device_id)

    lw = gui.test_get_login_widget()

    def _reload_devices():
        lw.reload_devices()

    await qt_thread_gateway.send_action(_reload_devices)

    no_device_w = lw.widget.layout().itemAt(0).widget()
    assert isinstance(no_device_w, LoginNoDevicesWidget)

import json
import os
import tempfile
import unittest

from src.redfish_server import RedfishServer
from src.handlers.systems_handler import SystemsHandler


class FakeRequestHandler:
    def __init__(self, path):
        self.path = path
        self.headers = {}
        self.status_code = None
        self.response_headers = {}
        self.body = b""
        self.wfile = self

    def send_response(self, code):
        self.status_code = code

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        return None

    def write(self, data):
        self.body += data


class RedfishServerPortTests(unittest.TestCase):
    def _write_temp_config(self, config):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(config, handle)
            return handle.name

    def test_initializes_when_vm_has_no_redfish_port(self):
        config = {
            "redfish_port": 9443,
            "vms": [
                {
                    "name": "vm-test",
                    "vcenter_host": "vcenter.example.com",
                    "vcenter_user": "administrator@vsphere.local",
                    "vcenter_password": "secret",
                }
            ],
        }

        temp_path = self._write_temp_config(config)

        try:
            server = RedfishServer(temp_path)
            self.assertEqual(server._get_effective_redfish_port(vm_config=server.config["vms"][0]), 9443)
        finally:
            os.unlink(temp_path)

    def test_uses_default_datacenter_folder_refresh_interval(self):
        temp_path = self._write_temp_config({
            "vms": [{
                "name": "vm-test",
                "vcenter_host": "vcenter.example.com",
                "vcenter_user": "administrator@vsphere.local",
                "vcenter_password": "secret",
            }]
        })

        try:
            server = RedfishServer(temp_path)
            self.assertEqual(server._get_datacenter_folder_refresh_interval_seconds(), 300)
        finally:
            os.unlink(temp_path)

    def test_uses_configured_datacenter_folder_refresh_interval(self):
        temp_path = self._write_temp_config({
            "vms": [{
                "name": "vm-test",
                "vcenter_host": "vcenter.example.com",
                "vcenter_user": "administrator@vsphere.local",
                "vcenter_password": "secret",
            }],
            "datacenter_folder_refresh_interval_seconds": 90,
        })

        try:
            server = RedfishServer(temp_path)
            self.assertEqual(server._get_datacenter_folder_refresh_interval_seconds(), 90)
        finally:
            os.unlink(temp_path)

    def test_prunes_stale_discovered_vms(self):
        config = {
            "vms": [
                {"name": "vm-stale", "discovered": True},
                {"name": "vm-active", "discovered": True},
                {"name": "vm-manual", "discovered": False},
            ]
        }

        server = RedfishServer(self._write_temp_config({
            "vms": [{
                "name": "vm-test",
                "vcenter_host": "vcenter.example.com",
                "vcenter_user": "administrator@vsphere.local",
                "vcenter_password": "secret",
            }]
        }))

        try:
            server._prune_stale_discovered_vms(config, {"vm-active"})
            self.assertEqual([vm["name"] for vm in config["vms"]], ["vm-active", "vm-manual"])
        finally:
            os.unlink(server.config_path)


class SystemsHandlerPayloadTests(unittest.TestCase):
    def test_get_system_info_includes_redfish_system_summary_fields(self):
        class FakeClient:
            def get_vm_info(self, vm_name):
                return {
                    "power_state": "poweredOn",
                    "cpu_count": 2,
                    "memory_mb": 4096,
                }

        handler = SystemsHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": FakeClient()},
            None,
        )

        data = handler._get_system_info("vm-test")

        self.assertEqual(data["Name"], "vm-test")
        self.assertEqual(data["SystemType"], "Virtual")
        self.assertEqual(data["PowerState"], "On")
        self.assertEqual(data["Bios"]["@odata.id"], "/redfish/v1/Systems/vm-test/Bios")
        self.assertEqual(data["Storage"]["@odata.id"], "/redfish/v1/Systems/vm-test/Storage")
        self.assertEqual(data["EthernetInterfaces"]["@odata.id"], "/redfish/v1/Systems/vm-test/EthernetInterfaces")
        self.assertEqual(data["Processors"]["@odata.id"], "/redfish/v1/Systems/vm-test/Processors")
        self.assertEqual(data["Memory"]["@odata.id"], "/redfish/v1/Systems/vm-test/Memory")
        self.assertEqual(data["NetworkInterfaces"]["@odata.id"], "/redfish/v1/Systems/vm-test/NetworkInterfaces")
        self.assertEqual(data["Links"]["Processors"][0]["@odata.id"], "/redfish/v1/Systems/vm-test/Processors")
        self.assertEqual(data["Links"]["Memory"][0]["@odata.id"], "/redfish/v1/Systems/vm-test/Memory")
        self.assertEqual(data["Links"]["NetworkInterfaces"][0]["@odata.id"], "/redfish/v1/Systems/vm-test/NetworkInterfaces")
        self.assertEqual(data["Links"]["EthernetInterfaces"][0]["@odata.id"], "/redfish/v1/Systems/vm-test/EthernetInterfaces")
        self.assertEqual(data["ProcessorSummary"]["Count"], 2)
        self.assertEqual(data["MemorySummary"]["TotalSystemMemoryGiB"], 4)

    def test_handle_get_serves_related_subresource_collections(self):
        handler = SystemsHandler(
            {"vm-test": {"name": "vm-test"}},
            {},
            None,
        )

        test_cases = [
            ("/redfish/v1/Systems/vm-test/Processors", "Processors"),
            ("/redfish/v1/Systems/vm-test/Memory", "Memory"),
            ("/redfish/v1/Systems/vm-test/NetworkInterfaces", "NetworkInterfaces"),
            ("/redfish/v1/Systems/vm-test/EthernetInterfaces", "EthernetInterfaces"),
        ]

        for path, expected_key in test_cases:
            with self.subTest(path=path):
                request_handler = FakeRequestHandler(path)
                handler.handle_get(request_handler, path)
                self.assertEqual(request_handler.status_code, 200)
                payload = json.loads(request_handler.body.decode("utf-8"))
                self.assertEqual(payload["@odata.id"], path)
                self.assertEqual(payload["Name"], f"{expected_key} Collection")
                self.assertEqual(payload["Members@odata.count"], 1)
                self.assertEqual(payload["Members"][0]["@odata.id"], f"{path}/1")


class AuthManagerTests(unittest.TestCase):
    def _make_auth(self, config=None):
        from src.auth.manager import AuthenticationManager
        return AuthenticationManager(config or {})

    def test_legacy_admin_password_always_accepted(self):
        auth = self._make_auth()
        self.assertTrue(auth._check_credentials("admin", "password"))

    def test_per_vm_credentials_accepted(self):
        auth = self._make_auth({
            "vms": [{"name": "vm-test", "redfish_user": "user1", "redfish_password": "secret1"}]
        })
        self.assertTrue(auth._check_credentials("user1", "secret1"))

    def test_unknown_credentials_rejected(self):
        auth = self._make_auth({
            "vms": [{"name": "vm-test", "redfish_user": "user1", "redfish_password": "secret1"}]
        })
        self.assertFalse(auth._check_credentials("user1", "wrong"))
        self.assertFalse(auth._check_credentials("hacker", "password"))


class SystemsPatchTests(unittest.TestCase):
    def _make_patch_request(self, vm_name, body_dict):
        import io
        body = json.dumps(body_dict).encode()

        class PatchReq(FakeRequestHandler):
            def __init__(self):
                super().__init__(f"/redfish/v1/Systems/{vm_name}")
                self.headers = {"Content-Length": str(len(body))}
                self.rfile = io.BytesIO(body)

        return PatchReq()

    def test_boot_patch_calls_vmware_set_boot_order(self):
        class FakeClient:
            def __init__(self):
                self.boot_order_set = None
            def get_vm_info(self, vm_name):
                return {"power_state": "poweredOn", "cpu_count": 2, "memory_mb": 4096}
            def set_vm_boot_order(self, vm_name, order):
                self.boot_order_set = order
                return True

        fake_client = FakeClient()
        handler = SystemsHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            None,
        )
        req = self._make_patch_request("vm-test", {"Boot": {"BootSourceOverrideTarget": "Cd", "BootSourceOverrideEnabled": "Once"}})
        handler._handle_system_patch(req, "vm-test", req.path)
        self.assertEqual(req.status_code, 200)
        self.assertIsNotNone(fake_client.boot_order_set)
        self.assertEqual(fake_client.boot_order_set[0], "cdrom")

    def test_boot_patch_returns_updated_system_object(self):
        class FakeClient:
            def get_vm_info(self, vm_name):
                return {"power_state": "poweredOff", "cpu_count": 1, "memory_mb": 2048}
            def set_vm_boot_order(self, vm_name, order):
                return True

        handler = SystemsHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": FakeClient()},
            None,
        )
        req = self._make_patch_request("vm-test", {"Boot": {"BootSourceOverrideTarget": "Pxe"}})
        handler._handle_system_patch(req, "vm-test", req.path)
        self.assertEqual(req.status_code, 200)
        payload = json.loads(req.body.decode("utf-8"))
        self.assertEqual(payload["Boot"]["BootSourceOverrideTarget"], "Pxe")

    def test_bios_patch_returns_501(self):
        import io
        handler = SystemsHandler({"vm-test": {"name": "vm-test"}}, {}, None)
        body = json.dumps({"Attributes": {"BootMode": "UEFI"}}).encode()
        req = FakeRequestHandler("/redfish/v1/Systems/vm-test/Bios")
        req.headers = {"Content-Length": str(len(body))}
        req.rfile = io.BytesIO(body)
        handler._handle_bios_patch(req, "vm-test", req.path)
        self.assertEqual(req.status_code, 501)

    def test_secure_boot_patch_returns_501(self):
        import io
        handler = SystemsHandler({"vm-test": {"name": "vm-test"}}, {}, None)
        body = json.dumps({"SecureBootEnable": False}).encode()
        req = FakeRequestHandler("/redfish/v1/Systems/vm-test/SecureBoot")
        req.headers = {"Content-Length": str(len(body))}
        req.rfile = io.BytesIO(body)
        handler._handle_secure_boot_patch(req, "vm-test", req.path)
        self.assertEqual(req.status_code, 501)


class VirtualMediaHandlerTests(unittest.TestCase):
    def _make_handler(self, config=None):
        from src.handlers.managers_handler import ManagersHandler
        return ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {},
            config or {},
        )

    def test_resolve_iso_path_from_datastore_bracket_path(self):
        handler = self._make_handler()
        result = handler._resolve_iso_path("[DS1] isos/rhcos.iso", None)
        self.assertEqual(result, "[DS1] isos/rhcos.iso")

    def test_resolve_iso_path_from_http_url_with_datastore(self):
        handler = self._make_handler({"virtual_media_datastore": "DS1"})
        result = handler._resolve_iso_path("http://bastion.example.com/images/rhcos.iso", "DS1", "vm-master-0")
        self.assertEqual(result, "[DS1] vm-master-0_rhcos.iso")

    def test_resolve_iso_path_returns_none_without_datastore(self):
        handler = self._make_handler()
        result = handler._resolve_iso_path("rhcos.iso", None, "vm-test")
        self.assertIsNone(result)

    def test_resolve_iso_path_bracket_datastore_config(self):
        handler = self._make_handler({"virtual_media_datastore": "[ISO_DS] isos"})
        result = handler._resolve_iso_path("http://host/rhcos.iso", "[ISO_DS] isos", "vm-test")
        self.assertEqual(result, "[ISO_DS] isos/vm-test_rhcos.iso")

    def test_virtual_media_get_shows_not_inserted_by_default(self):
        from src.handlers.managers_handler import ManagersHandler
        handler = ManagersHandler({"vm-test": {"name": "vm-test"}}, {}, {})
        req = FakeRequestHandler("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD")
        handler._handle_virtual_media_get(req, "vm-test-bmc", req.path)
        self.assertEqual(req.status_code, 200)
        payload = json.loads(req.body.decode("utf-8"))
        self.assertFalse(payload["Inserted"])
        self.assertEqual(payload["ConnectedVia"], "NotConnected")

    def test_insert_media_stores_state_and_calls_mount(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.mounted = None
                self.uploaded_from = None
                self.uploaded_to = None
            def get_iso_status(self, vm_name):
                return {"inserted": False, "image": None, "connected": False}
            def upload_iso_to_datastore(self, source_url, datastore_path):
                self.uploaded_from = source_url
                self.uploaded_to = datastore_path
                return True
            def mount_iso(self, vm_name, iso_path):
                self.mounted = iso_path
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {"virtual_media_datastore": "DS1"},
        )

        body = json.dumps({"Image": "http://bastion/rhcos.iso", "WriteProtected": True}).encode()

        class PostReq(FakeRequestHandler):
            def __init__(self):
                super().__init__("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia")
                self.headers = {"Content-Length": str(len(body))}
                self.rfile = io.BytesIO(body)

        req = PostReq()
        handler._handle_insert_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(req.status_code, 204)
        # Upload should have been triggered for an HTTP URL
        self.assertEqual(fake_client.uploaded_from, "http://bastion/rhcos.iso")
        self.assertEqual(fake_client.uploaded_to, "[DS1] vm-test_rhcos.iso")
        self.assertEqual(fake_client.mounted, "[DS1] vm-test_rhcos.iso")
        state = handler._get_media_state("vm-test", "CD")
        self.assertTrue(state["inserted"])
        self.assertEqual(state["image"], "http://bastion/rhcos.iso")

    def test_insert_media_skips_upload_for_datastore_path(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.upload_called = False
                self.mounted = None
            def get_iso_status(self, vm_name):
                return {"inserted": False, "image": None, "connected": False}
            def upload_iso_to_datastore(self, source_url, datastore_path):
                self.upload_called = True
                return True
            def mount_iso(self, vm_name, iso_path):
                self.mounted = iso_path
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {"virtual_media_datastore": "DS1"},
        )

        # Image is already a datastore path — no upload should happen
        body = json.dumps({"Image": "[DS1] isos/rhcos.iso"}).encode()

        class PostReq(FakeRequestHandler):
            def __init__(self):
                super().__init__("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia")
                self.headers = {"Content-Length": str(len(body))}
                self.rfile = io.BytesIO(body)

        req = PostReq()
        handler._handle_insert_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(req.status_code, 204)
        self.assertFalse(fake_client.upload_called)
        self.assertEqual(fake_client.mounted, "[DS1] isos/rhcos.iso")

    def test_eject_media_clears_state_and_calls_unmount(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.ejected = False
            def get_iso_status(self, vm_name):
                return {"inserted": True, "image": "[DS1] rhcos.iso", "connected": True}
            def unmount_iso(self, vm_name, force=False):
                self.ejected = True
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {},
        )
        # Force initial state from the "already mounted" VMware status
        handler._get_media_state("vm-test", "CD")

        req = FakeRequestHandler("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia")
        req.rfile = io.BytesIO(b"")
        handler._handle_eject_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(req.status_code, 204)
        self.assertTrue(fake_client.ejected)
        state = handler._get_media_state("vm-test", "CD")
        self.assertFalse(state["inserted"])

    def test_eject_media_deletes_file_when_delete_on_eject_enabled(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.ejected = False
                self.deleted_path = None
            def get_iso_status(self, vm_name):
                # File was previously uploaded via our system — name carries the vm prefix
                return {"inserted": True, "image": "[DS1] vm-test_rhcos.iso", "connected": True}
            def unmount_iso(self, vm_name, force=False):
                self.ejected = True
                return True
            def datastore_file_exists(self, path):
                return True
            def delete_datastore_file(self, path):
                self.deleted_path = path
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {"delete_on_eject": True},
        )
        handler._get_media_state("vm-test", "CD")

        req = FakeRequestHandler("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia")
        req.rfile = io.BytesIO(b"")
        handler._handle_eject_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(req.status_code, 204)
        self.assertEqual(fake_client.deleted_path, "[DS1] vm-test_rhcos.iso")

    def test_eject_media_skips_delete_when_file_not_on_datastore(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.delete_called = False
            def get_iso_status(self, vm_name):
                return {"inserted": True, "image": "[DS1] vm-test_rhcos.iso", "connected": True}
            def unmount_iso(self, vm_name, force=False):
                return True
            def datastore_file_exists(self, path):
                return False
            def delete_datastore_file(self, path):
                self.delete_called = True
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {"delete_on_eject": True},
        )
        handler._get_media_state("vm-test", "CD")

        req = FakeRequestHandler("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia")
        req.rfile = io.BytesIO(b"")
        handler._handle_eject_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(req.status_code, 204)
        self.assertFalse(fake_client.delete_called)

    def test_eject_media_does_not_delete_when_delete_on_eject_disabled(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.delete_called = False
            def get_iso_status(self, vm_name):
                return {"inserted": True, "image": "[DS1] rhcos.iso", "connected": True}
            def unmount_iso(self, vm_name, force=False):
                return True
            def delete_datastore_file(self, path):
                self.delete_called = True
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {"delete_on_eject": False},
        )
        handler._get_media_state("vm-test", "CD")

        req = FakeRequestHandler("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia")
        req.rfile = io.BytesIO(b"")
        handler._handle_eject_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(req.status_code, 204)
        self.assertFalse(fake_client.delete_called)

    def test_delete_on_eject_resolves_http_url_to_datastore_path(self):
        import io
        from src.handlers.managers_handler import ManagersHandler

        class FakeClient:
            def __init__(self):
                self.deleted_path = None
            def get_iso_status(self, vm_name):
                # Image stored as HTTP URL
                return {"inserted": True, "image": "http://bastion/images/rhcos.iso", "connected": True}
            def unmount_iso(self, vm_name, force=False):
                return True
            def datastore_file_exists(self, path):
                return True
            def delete_datastore_file(self, path):
                self.deleted_path = path
                return True

        fake_client = FakeClient()
        handler = ManagersHandler(
            {"vm-test": {"name": "vm-test"}},
            {"vm-test": fake_client},
            {"delete_on_eject": True, "virtual_media_datastore": "DS1"},
        )
        handler._get_media_state("vm-test", "CD")

        req = FakeRequestHandler("/redfish/v1/Managers/vm-test-bmc/VirtualMedia/CD/Actions/VirtualMedia.EjectMedia")
        req.rfile = io.BytesIO(b"")
        handler._handle_eject_media(req, "vm-test", "vm-test-bmc", "CD")
        self.assertEqual(fake_client.deleted_path, "[DS1] vm-test_rhcos.iso")


class ManagersPostRoutingTests(unittest.TestCase):
    """Test that POST requests to /redfish/v1/Managers are properly routed"""

    def _write_temp_config(self, config):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(config, handle)
            return handle.name

    def test_insert_media_post_routes_to_managers_handler(self):
        """Test that POST to VirtualMedia InsertMedia endpoint is not 404"""
        import io
        from unittest.mock import MagicMock, patch
        from src.handlers.redfish_handler import RedfishHandler
        from src.handlers.managers_handler import ManagersHandler

        upload_called = []
        mount_called = []

        class FakeClient:
            def get_iso_status(self, vm_name):
                return {"inserted": False, "image": None, "connected": False}
            def upload_iso_to_datastore(self, source_url, datastore_path):
                upload_called.append((source_url, datastore_path))
                return True
            def mount_iso(self, vm_name, datastore_path):
                mount_called.append((vm_name, datastore_path))
                return True

        vm_config = {"name": "vm-1", "vcenter_host": "h", "vcenter_user": "u", "vcenter_password": "p",
                     "redfish_user": "admin", "redfish_password": "password"}
        config = {
            "vms": [vm_config],
            "virtual_media_datastore": "DS1",
            "delete_on_eject": False,
            "redfish_port": 8443,
            "disable_ssl": True,
        }

        handler = RedfishHandler([vm_config], config)
        handler.vmware_clients["vm-1"] = FakeClient()
        handler.managers_handler.vmware_clients["vm-1"] = FakeClient()
        handler.managers_handler.config = config

        body = json.dumps({"Image": "http://172.16.15.6/iso/test.iso"}).encode()
        req = FakeRequestHandler("/redfish/v1/Managers/vm-1-bmc/VirtualMedia/CD/Actions/VirtualMedia.InsertMedia")
        req.headers = {"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="}  # admin:password
        req.rfile = io.BytesIO(body)
        req.headers["Content-Length"] = str(len(body))

        # Should NOT return 404 - should reach the managers handler
        handler.managers_handler.handle_post(req, req.path)
        self.assertNotEqual(req.status_code, 404)


class SSLCertificateGenerationTests(unittest.TestCase):
    """Test self-signed SSL certificate generation"""

    def _write_temp_config(self, config):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(config, handle)
            return handle.name

    def test_generate_self_signed_cert_creates_files(self):
        """Test that self-signed certificate generation creates cert and key files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "server.crt")
            key_path = os.path.join(tmpdir, "server.key")

            config = {
                "redfish_port": 8443,
                "disable_ssl": False,
                "vms": [{"name": "vm-test", "vcenter_host": "vcenter.example.com",
                         "vcenter_user": "admin", "vcenter_password": "password"}]
            }
            config_path = self._write_temp_config(config)
            try:
                server = RedfishServer(config_path)
                result = server._generate_self_signed_cert(cert_path, key_path)

                self.assertTrue(result)
                self.assertTrue(os.path.exists(cert_path))
                self.assertTrue(os.path.exists(key_path))

                with open(cert_path, 'r') as f:
                    self.assertIn("BEGIN CERTIFICATE", f.read())
                with open(key_path, 'r') as f:
                    self.assertIn("BEGIN RSA PRIVATE KEY", f.read())
            finally:
                os.unlink(config_path)

    def test_generate_self_signed_cert_sets_permissions(self):
        """Test that certificate and key file permissions are set correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "server.crt")
            key_path = os.path.join(tmpdir, "server.key")

            config = {
                "redfish_port": 8443,
                "disable_ssl": False,
                "vms": [{"name": "vm-test", "vcenter_host": "vcenter.example.com",
                         "vcenter_user": "admin", "vcenter_password": "password"}]
            }
            config_path = self._write_temp_config(config)
            try:
                server = RedfishServer(config_path)
                server._generate_self_signed_cert(cert_path, key_path)

                self.assertEqual(os.stat(key_path).st_mode & 0o777, 0o600)
                self.assertEqual(os.stat(cert_path).st_mode & 0o777, 0o644)
            finally:
                os.unlink(config_path)

    def test_generate_self_signed_cert_creates_directory(self):
        """Test that certificate directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_dir = os.path.join(tmpdir, "ssl", "nested", "dir")
            cert_path = os.path.join(cert_dir, "server.crt")
            key_path = os.path.join(cert_dir, "server.key")

            config = {
                "redfish_port": 8443,
                "disable_ssl": False,
                "vms": [{"name": "vm-test", "vcenter_host": "vcenter.example.com",
                         "vcenter_user": "admin", "vcenter_password": "password"}]
            }
            config_path = self._write_temp_config(config)
            try:
                self.assertFalse(os.path.exists(cert_dir))
                server = RedfishServer(config_path)
                result = server._generate_self_signed_cert(cert_path, key_path)

                self.assertTrue(result)
                self.assertTrue(os.path.exists(cert_dir))
                self.assertTrue(os.path.exists(cert_path))
                self.assertTrue(os.path.exists(key_path))
            finally:
                os.unlink(config_path)

    def test_setup_ssl_returns_context_with_existing_certs(self):
        """Test that _setup_ssl returns an SSL context when certificates exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_path = os.path.join(tmpdir, "server.crt")
            key_path = os.path.join(tmpdir, "server.key")

            config = {
                "redfish_port": 8443,
                "disable_ssl": False,
                "vms": [{"name": "vm-test", "vcenter_host": "vcenter.example.com",
                         "vcenter_user": "admin", "vcenter_password": "password"}]
            }
            config_path = self._write_temp_config(config)
            try:
                server = RedfishServer(config_path)
                server._generate_self_signed_cert(cert_path, key_path)
                server.config["ssl"] = {"cert_path": cert_path, "key_path": key_path}

                context = server._setup_ssl("vm-test", 8443)

                self.assertIsNotNone(context)
                self.assertTrue(hasattr(context, 'wrap_socket'))
            finally:
                os.unlink(config_path)


class MediaOperationsBootOrderTests(unittest.TestCase):
    def test_create_boot_devices_uses_hardware_device_keys(self):
        try:
            from pyVmomi import vim
            from src.vmware.media_operations import MediaOperations
        except ImportError:
            self.skipTest("pyVmomi not installed")

        from unittest.mock import MagicMock

        cdrom = vim.vm.device.VirtualCdrom()
        cdrom.key = 3000
        disk = vim.vm.device.VirtualDisk()
        disk.key = 2000
        nic = vim.vm.device.VirtualEthernetCard()
        nic.key = 4000

        vm = MagicMock()
        vm.config.hardware.device = [disk, cdrom, nic]

        ops = MediaOperations(MagicMock(), MagicMock())
        device_keys = ops._collect_boot_device_keys(vm)

        self.assertEqual(device_keys['cdrom'], [3000])
        self.assertEqual(device_keys['disk'], [2000])
        self.assertEqual(device_keys['network'], [4000])

        boot_devices = [
            ops._create_boot_device(device_type, device_keys)
            for device_type in ['cdrom', 'disk', 'network']
        ]

        self.assertEqual(len(boot_devices), 3)
        self.assertEqual(type(boot_devices[0]).__name__, 'BootableCdromDevice')
        self.assertEqual(boot_devices[1].deviceKey, 2000)
        self.assertEqual(boot_devices[2].deviceKey, 4000)

    def test_hdd_boot_order_builds_disk_before_cdrom(self):
        try:
            from pyVmomi import vim
            from src.vmware.media_operations import MediaOperations
        except ImportError:
            self.skipTest("pyVmomi not installed")

        from unittest.mock import MagicMock

        cdrom = vim.vm.device.VirtualCdrom()
        cdrom.key = 16000
        disk = vim.vm.device.VirtualDisk()
        disk.key = 2000
        nic = vim.vm.device.VirtualEthernetCard()
        nic.key = 4000

        vm = MagicMock()
        vm.config.hardware.device = [disk, cdrom, nic]

        ops = MediaOperations(MagicMock(), MagicMock())
        device_keys = ops._collect_boot_device_keys(vm)
        boot_devices = [
            ops._create_boot_device(device_type, device_keys)
            for device_type in ['disk', 'cdrom', 'network']
        ]

        self.assertEqual(len(boot_devices), 3)
        self.assertEqual(boot_devices[0].deviceKey, 2000)
        self.assertEqual(type(boot_devices[1]).__name__, 'BootableCdromDevice')
        self.assertEqual(boot_devices[2].deviceKey, 4000)


class VMwareReconnectTests(unittest.TestCase):
    def test_get_vm_info_reconnects_on_not_authenticated(self):
        from unittest.mock import MagicMock
        from pyVmomi import vim
        from src.vmware_client import VMwareClient

        client = VMwareClient.__new__(VMwareClient)
        client.host = 'vcenter.example.com'
        client.connection = MagicMock()
        client.vm_ops = MagicMock()
        client.power_ops = MagicMock()
        client.media_ops = MagicMock()

        client.vm_ops.get_vm_info.side_effect = [
            vim.fault.NotAuthenticated(),
            {'name': 'vm-1', 'power_state': 'poweredOff'},
        ]

        result = client.get_vm_info('vm-1')

        client.connection.ensure_authenticated.assert_called()
        client.connection.reconnect.assert_called_once()
        self.assertEqual(client.vm_ops.connection, client.connection)
        self.assertEqual(client.power_ops.connection, client.connection)
        self.assertEqual(client.media_ops.connection, client.connection)
        self.assertEqual(result['name'], 'vm-1')
        self.assertEqual(client.vm_ops.get_vm_info.call_count, 2)


if __name__ == "__main__":
    unittest.main()

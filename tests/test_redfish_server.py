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


if __name__ == "__main__":
    unittest.main()

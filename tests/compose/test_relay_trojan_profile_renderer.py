import unittest

from agentplane.domain.service.materialize import render_clash_local_profile


class RelayTrojanProfileRendererTests(unittest.TestCase):
    def test_render_profile_keeps_effective_rules_and_rewrites_proxy_sets(self) -> None:
        source = {
            "mode": "rule",
            "proxies": [
                {"name": "旧节点A", "type": "ss", "server": "a.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "x"},
                {"name": "旧节点B", "type": "ss", "server": "b.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "y"},
            ],
            "proxy-groups": [
                {"name": "国外流量", "type": "select", "proxies": ["旧节点A", "旧节点B", "直接连接"]},
                {"name": "GPT", "type": "select", "proxies": ["国外流量", "旧节点A", "直接连接"]},
                {"name": "Steam_API", "type": "select", "proxies": ["国外流量", "DIRECT", "旧节点B"]},
            ],
            "rules": ["DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
        }
        merge = {
            "prepend__rules": [
                "DOMAIN-SUFFIX,zzzai.fun,DIRECT",
                "DOMAIN-SUFFIX,cloudflare.com,GPT",
            ]
        }

        rendered = render_clash_local_profile(
            source,
            merge_template=merge,
            node_name="Prod2|Relay",
            server="relay.zzzai.fun",
            port=24443,
            password="test-password",
            sni="relay.zzzai.fun",
        )

        self.assertEqual(
            {
                "name": "Prod2|Relay",
                "type": "trojan",
                "server": "relay.zzzai.fun",
                "port": 24443,
                "password": "test-password",
                "sni": "relay.zzzai.fun",
                "udp": True,
                "skip-cert-verify": False,
            },
            rendered["proxies"][0],
        )
        self.assertEqual(["Prod2|Relay", "直接连接"], rendered["proxy-groups"][0]["proxies"])
        self.assertEqual(["国外流量", "Prod2|Relay", "直接连接"], rendered["proxy-groups"][1]["proxies"])
        self.assertEqual(["国外流量", "DIRECT", "Prod2|Relay"], rendered["proxy-groups"][2]["proxies"])
        self.assertEqual(
            [
                "DOMAIN-SUFFIX,zzzai.fun,DIRECT",
                "DOMAIN-SUFFIX,cloudflare.com,GPT",
                "DOMAIN-SUFFIX,openai.com,GPT",
                "MATCH,国外流量",
            ],
            rendered["rules"],
        )


if __name__ == "__main__":
    unittest.main()


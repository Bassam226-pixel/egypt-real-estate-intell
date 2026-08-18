#!/usr/bin/env python3
"""
Grafana Setup Test Script
This script tests the Grafana setup and verifies all components are working.
"""

import requests
import sys
import time
from datetime import datetime

class GrafanaTest:
    def __init__(self, base_url="http://localhost:3000", username="admin", password="admin"):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.results = []
    
    def test_connection(self):
        """Test basic connection to Grafana"""
        try:
            response = self.session.get(f"{self.base_url}/api/health")
            if response.status_code == 200:
                data = response.json()
                self.results.append({
                    "test": "Connection",
                    "status": "PASS",
                    "message": f"Connected to Grafana v{data.get('version', 'unknown')}"
                })
                return True
            else:
                self.results.append({
                    "test": "Connection",
                    "status": "FAIL",
                    "message": f"HTTP {response.status_code}"
                })
                return False
        except Exception as e:
            self.results.append({
                "test": "Connection",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_authentication(self):
        """Test authentication"""
        try:
            response = self.session.get(f"{self.base_url}/api/org")
            if response.status_code == 200:
                data = response.json()
                self.results.append({
                    "test": "Authentication",
                    "status": "PASS",
                    "message": f"Authenticated as org '{data.get('name', 'unknown')}'"
                })
                return True
            else:
                self.results.append({
                    "test": "Authentication",
                    "status": "FAIL",
                    "message": f"HTTP {response.status_code}"
                })
                return False
        except Exception as e:
            self.results.append({
                "test": "Authentication",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_datasources(self):
        """Test data sources"""
        try:
            response = self.session.get(f"{self.base_url}/api/datasources")
            if response.status_code == 200:
                datasources = response.json()
                self.results.append({
                    "test": "Data Sources",
                    "status": "PASS",
                    "message": f"Found {len(datasources)} data source(s)"
                })
                return True
            else:
                self.results.append({
                    "test": "Data Sources",
                    "status": "FAIL",
                    "message": f"HTTP {response.status_code}"
                })
                return False
        except Exception as e:
            self.results.append({
                "test": "Data Sources",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_dashboards(self):
        """Test dashboards"""
        try:
            response = self.session.get(f"{self.base_url}/api/search")
            if response.status_code == 200:
                dashboards = response.json()
                self.results.append({
                    "test": "Dashboards",
                    "status": "PASS",
                    "message": f"Found {len(dashboards)} dashboard(s)"
                })
                return True
            else:
                self.results.append({
                    "test": "Dashboards",
                    "status": "FAIL",
                    "message": f"HTTP {response.status_code}"
                })
                return False
        except Exception as e:
            self.results.append({
                "test": "Dashboards",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_image_renderer(self):
        """Test image renderer"""
        try:
            # Try to render a simple dashboard
            response = self.session.get(
                f"{self.base_url}/render/d/home-dashboard",
                params={'orgId': 1, 'width': 800, 'height': 600}
            )
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    self.results.append({
                        "test": "Image Renderer",
                        "status": "PASS",
                        "message": "Image renderer is working"
                    })
                    return True
                else:
                    self.results.append({
                        "test": "Image Renderer",
                        "status": "FAIL",
                        "message": f"Expected image, got {content_type}"
                    })
                    return False
            else:
                self.results.append({
                    "test": "Image Renderer",
                    "status": "FAIL",
                    "message": f"HTTP {response.status_code}"
                })
                return False
        except Exception as e:
            self.results.append({
                "test": "Image Renderer",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def test_plugins(self):
        """Test installed plugins"""
        try:
            response = self.session.get(f"{self.base_url}/api/plugins")
            if response.status_code == 200:
                plugins = response.json()
                self.results.append({
                    "test": "Plugins",
                    "status": "PASS",
                    "message": f"Found {len(plugins)} plugin(s)"
                })
                return True
            else:
                self.results.append({
                    "test": "Plugins",
                    "status": "FAIL",
                    "message": f"HTTP {response.status_code}"
                })
                return False
        except Exception as e:
            self.results.append({
                "test": "Plugins",
                "status": "FAIL",
                "message": str(e)
            })
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("Grafana Setup Test")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"URL: {self.base_url}")
        print("=" * 60)
        print()
        
        # Run tests
        tests = [
            self.test_connection,
            self.test_authentication,
            self.test_datasources,
            self.test_dashboards,
            self.test_plugins,
            self.test_image_renderer
        ]
        
        for test in tests:
            print(f"Running {test.__doc__}...")
            test()
            time.sleep(0.5)
        
        # Print results
        print()
        print("=" * 60)
        print("Test Results")
        print("=" * 60)
        
        passed = 0
        failed = 0
        
        for result in self.results:
            status = result['status']
            test_name = result['test']
            message = result['message']
            
            if status == 'PASS':
                print(f"✓ {test_name}: {message}")
                passed += 1
            else:
                print(f"✗ {test_name}: {message}")
                failed += 1
        
        print("=" * 60)
        print(f"Total: {len(self.results)} tests, {passed} passed, {failed} failed")
        print("=" * 60)
        
        return failed == 0


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Grafana Setup Test')
    parser.add_argument('--url', default='http://localhost:3000', help='Grafana URL')
    parser.add_argument('--username', default='admin', help='Grafana username')
    parser.add_argument('--password', default='admin', help='Grafana password')
    
    args = parser.parse_args()
    
    # Run tests
    tester = GrafanaTest(args.url, args.username, args.password)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
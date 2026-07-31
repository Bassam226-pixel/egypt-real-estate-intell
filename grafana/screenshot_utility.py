#!/usr/bin/env python3
"""
Grafana Dashboard Screenshot Utility
This script captures screenshots of Grafana dashboards using the Grafana API.
"""

import requests
import time
import os
import sys
from datetime import datetime
from pathlib import Path
import json

class GrafanaScreenshot:
    def __init__(self, base_url="http://localhost:3000", username="admin", password="admin"):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.api_key = None
        self.session = requests.Session()
        self.session.auth = (username, password)
        
    def authenticate(self):
        """Authenticate with Grafana using basic auth"""
        try:
            response = self.session.get(f"{self.base_url}/api/org")
            if response.status_code == 200:
                print(f"✓ Connected to Grafana at {self.base_url}")
                return True
            else:
                print(f"✗ Failed to connect to Grafana: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def get_dashboards(self):
        """Get list of all dashboards"""
        try:
            response = self.session.get(f"{self.base_url}/api/search")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get dashboards: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting dashboards: {e}")
            return []
    
    def get_dashboard_by_uid(self, uid):
        """Get dashboard by UID"""
        try:
            response = self.session.get(f"{self.base_url}/api/dashboards/uid/{uid}")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get dashboard {uid}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error getting dashboard {uid}: {e}")
            return None
    
    def capture_screenshot(self, dashboard_uid, output_path, width=1920, height=1080, time_range=None):
        """
        Capture screenshot of a dashboard
        
        Args:
            dashboard_uid: Dashboard UID
            output_path: Path to save screenshot
            width: Screenshot width (default: 1920)
            height: Screenshot height (default: 1080)
            time_range: Optional time range (e.g., "now-1h", "now-24h", "now-7d")
        """
        try:
            # Build render URL
            render_url = f"{self.base_url}/render/d/{dashboard_uid}"
            
            # Add parameters
            params = {
                'orgId': 1,
                'width': width,
                'height': height,
                'timezone': 'Africa/Cairo'
            }
            
            if time_range:
                params['from'] = time_range
                params['to'] = 'now'
            
            # Make request to render endpoint
            print(f"Capturing screenshot for dashboard: {dashboard_uid}")
            response = self.session.get(render_url, params=params, stream=True)
            
            if response.status_code == 200:
                # Ensure output directory exists
                output_dir = Path(output_path).parent
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Save screenshot
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(output_path)
                print(f"✓ Screenshot saved: {output_path} ({file_size:,} bytes)")
                return True
            else:
                print(f"✗ Failed to capture screenshot: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"✗ Error capturing screenshot: {e}")
            return False
    
    def capture_all_dashboards(self, output_dir="screenshots", time_range=None):
        """
        Capture screenshots of all dashboards
        
        Args:
            output_dir: Directory to save screenshots
            time_range: Optional time range
        """
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get all dashboards
        dashboards = self.get_dashboards()
        
        if not dashboards:
            print("No dashboards found")
            return []
        
        print(f"\nFound {len(dashboards)} dashboards")
        print("-" * 60)
        
        captured_files = []
        
        for dashboard in dashboards:
            uid = dashboard.get('uid')
            title = dashboard.get('title', 'untitled')
            
            if not uid:
                continue
            
            # Create filename from title
            safe_title = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in title)
            filename = f"{safe_title}.png"
            output_path = os.path.join(output_dir, filename)
            
            # Capture screenshot
            if self.capture_screenshot(uid, output_path, time_range=time_range):
                captured_files.append(output_path)
            
            # Small delay between captures
            time.sleep(1)
        
        return captured_files
    
    def capture_dashboard_with_panels(self, dashboard_uid, output_dir="screenshots", time_range=None):
        """
        Capture individual panels from a dashboard
        
        Args:
            dashboard_uid: Dashboard UID
            output_dir: Directory to save screenshots
            time_range: Optional time range
        """
        # Get dashboard details
        dashboard_data = self.get_dashboard_by_uid(dashboard_uid)
        
        if not dashboard_data:
            print(f"Dashboard {dashboard_uid} not found")
            return []
        
        dashboard = dashboard_data.get('dashboard', {})
        panels = dashboard.get('panels', [])
        title = dashboard.get('title', 'untitled')
        
        print(f"\nCapturing panels from: {title}")
        print(f"Found {len(panels)} panels")
        
        # Create output directory
        panel_dir = os.path.join(output_dir, f"{dashboard_uid}_panels")
        Path(panel_dir).mkdir(parents=True, exist_ok=True)
        
        captured_files = []
        
        for panel in panels:
            panel_id = panel.get('id')
            panel_title = panel.get('title', f'panel_{panel_id}')
            
            if not panel_id:
                continue
            
            # Create filename from panel title
            safe_title = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in panel_title)
            filename = f"{safe_title}.png"
            output_path = os.path.join(panel_dir, filename)
            
            # Capture panel screenshot
            try:
                render_url = f"{self.base_url}/render/d/{dashboard_uid}/?orgId=1&from=now-1h&to=now&panelId={panel_id}&width=800&height=400"
                
                response = self.session.get(render_url, stream=True)
                
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    file_size = os.path.getsize(output_path)
                    print(f"  ✓ Panel '{panel_title}' saved: {filename} ({file_size:,} bytes)")
                    captured_files.append(output_path)
                else:
                    print(f"  ✗ Failed to capture panel '{panel_title}': {response.status_code}")
                    
            except Exception as e:
                print(f"  ✗ Error capturing panel '{panel_title}': {e}")
            
            # Small delay between captures
            time.sleep(0.5)
        
        return captured_files
    
    def export_dashboard_json(self, dashboard_uid, output_path):
        """
        Export dashboard JSON
        
        Args:
            dashboard_uid: Dashboard UID
            output_path: Path to save JSON
        """
        dashboard_data = self.get_dashboard_by_uid(dashboard_uid)
        
        if dashboard_data:
            dashboard = dashboard_data.get('dashboard', {})
            
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(dashboard, f, indent=2)
            
            print(f"✓ Dashboard JSON exported: {output_path}")
            return True
        else:
            print(f"✗ Failed to export dashboard {dashboard_uid}")
            return False


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Grafana Dashboard Screenshot Utility')
    parser.add_argument('--url', default='http://localhost:3000', help='Grafana URL')
    parser.add_argument('--username', default='admin', help='Grafana username')
    parser.add_argument('--password', default='admin', help='Grafana password')
    parser.add_argument('--action', choices=['list', 'capture', 'capture-all', 'capture-panels', 'export'], 
                       default='list', help='Action to perform')
    parser.add_argument('--dashboard', help='Dashboard UID')
    parser.add_argument('--output', default='screenshots', help='Output directory or file')
    parser.add_argument('--time-range', help='Time range (e.g., now-1h, now-24h, now-7d)')
    parser.add_argument('--width', type=int, default=1920, help='Screenshot width')
    parser.add_argument('--height', type=int, default=1080, help='Screenshot height')
    
    args = parser.parse_args()
    
    # Initialize screenshot utility
    grafana = GrafanaScreenshot(args.url, args.username, args.password)
    
    # Authenticate
    if not grafana.authenticate():
        sys.exit(1)
    
    # Perform action
    if args.action == 'list':
        dashboards = grafana.get_dashboards()
        print(f"\nAvailable dashboards ({len(dashboards)}):")
        print("-" * 60)
        for d in dashboards:
            print(f"  UID: {d.get('uid'):20} | Title: {d.get('title')}")
    
    elif args.action == 'capture':
        if not args.dashboard:
            print("Error: --dashboard required for capture action")
            sys.exit(1)
        
        output_path = args.output
        if os.path.isdir(output_path):
            output_path = os.path.join(output_path, f"{args.dashboard}.png")
        
        grafana.capture_screenshot(args.dashboard, output_path, args.width, args.height, args.time_range)
    
    elif args.action == 'capture-all':
        captured = grafana.capture_all_dashboards(args.output, args.time_range)
        print(f"\n✓ Captured {len(captured)} screenshots")
    
    elif args.action == 'capture-panels':
        if not args.dashboard:
            print("Error: --dashboard required for capture-panels action")
            sys.exit(1)
        
        captured = grafana.capture_dashboard_with_panels(args.dashboard, args.output, args.time_range)
        print(f"\n✓ Captured {len(captured)} panel screenshots")
    
    elif args.action == 'export':
        if not args.dashboard:
            print("Error: --dashboard required for export action")
            sys.exit(1)
        
        grafana.export_dashboard_json(args.dashboard, args.output)


if __name__ == '__main__':
    main()
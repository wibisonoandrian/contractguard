# ContractGuard Chrome Extension

Auto-detects contract address on Etherscan-family explorer pages and overlays a risk verdict badge. Click extension icon for full analysis.

## Install (developer mode)

1. Start the API server:
   ```bash
   cd ~/projects/contractguard
   ./venv/bin/python -m contractguard.cli serve --port 8766
   ```

2. Open Chrome → `chrome://extensions/`

3. Enable **Developer mode** (top-right toggle)

4. Click **Load unpacked** → pick the `extension/` directory

5. Pin the extension to toolbar (optional)

## Usage

- Visit any Etherscan, BscScan, BaseScan, Arbiscan, or PolygonScan address page
- Bottom-right corner: live verdict badge appears
- Click the extension icon for detailed report
- Settings: change API endpoint (default `http://localhost:8766`)

## Pages Supported

- `etherscan.io/address/<addr>`
- `bscscan.com/address/<addr>`
- `basescan.org/address/<addr>`
- `arbiscan.io/address/<addr>`
- `polygonscan.com/address/<addr>`

## Icons

Place 16x16, 48x48, 128x128 PNG icons in `extension/icons/`. (Empty for now — extension works without, just shows blank icon.)

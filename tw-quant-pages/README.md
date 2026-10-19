# 台股量化策略研究站 — GitHub Pages 免費版

## 上線（不需 Render）
1. GitHub 建立 **Public** repository（例如 `tw-quant-pages`）。請勿上傳個人持倉、API 密碼或敏感資料。
2. 上傳此資料夾內的**全部檔案及資料夾**至 repo 根目錄，包含隱藏的 `.github/workflows/update.yml`。ZIP 請先解壓縮。
3. Repository → **Settings → Actions → General**，Workflow permissions 設為 **Read and write permissions**（若允許）。
4. Repository → **Actions → Daily Taiwan Stock Signals → Run workflow**，等待完成。此操作首次補齊歷史日線並產生 `docs/data/latest.json`。
5. Repository → **Settings → Pages → Build and deployment**，Source 選 **Deploy from a branch**、Branch `main`、Folder `/docs`，儲存。
6. 網址格式：`https://<你的GitHub帳號>.github.io/<repo名稱>/`。在手機 Safari 開啟即可。

## 排程
工作流程每週一到五 UTC 09:30（台灣 17:30）執行，GitHub 排程可能延遲或暫停。若資料日期未更新，請檢查 Actions 紀錄；休市日不會有新日線。

## 設定股票池
修改 `watchlist.json`。目前為 10 檔上市股票。免費版刻意限制為追蹤清單而非全市場掃描；大量請求可能被 TWSE 限流。修改後在 Actions 手動重新執行。

## 資料與策略
- 使用 TWSE `https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=YYYYMM01&stockNo=2330` 月歷史行情。
- 不需要前端跨域呼叫 API，所有資料由 Actions 抓取後寫入靜態 JSON。
- 沿用 V3.3 MA20/MA60、20日突破、量比、RSI、ATR 策略規則。不是波浪自動辨識，也不是實時買賣單。
- `docs/data/history.json` 為日線快取；`docs/data/ledger.json` 保存訊號快照與**假設性**模擬交易；`docs/data/latest.json` 供網頁顯示。
- 推薦日之後下一交易日**收盤價**當模擬進場價，無法證明實際可成交；出場以收盤判斷。假設每筆 1000 股、買賣手續費各 0.1425%、一般股票賣出證交稅 0.3%，不含滑價與最低費用。
- 週報目前為每週**已實現**損益；未實現損益獨立呈現。未包含資金限制、持倉集中度與真實帳戶權益曲線，因此**不提供最大回撤數值**，避免誤導。
- 公開 repo 代表策略快照與模擬交易資料也公開。不得用於私人實際交易紀錄。

## 測試
在專案根目錄執行 `python scripts/update.py`，需要網路連線；`python -m http.server 8000 --directory docs` 本機預覽（先完成首次資料生成）。

## 重要
此專案為研究原型，非投資建議。證交所 API 格式或存取限制若變更，需更新擷取程式。Github Actions 的免費服務條款與限制以官方公告為準。

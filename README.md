# 台股六策略研究站 · research-v2.1

已接入六個日線價格型態辨識器與篩選介面。研究候選不等於有效買進訊號。沒有下單功能，尚未實作完整持倉、資金與交易成本回測引擎；停損與目標為參考欄位，持倉規則詳見 STRATEGY_SPEC.md。

## 更新步驟

1. 先下載備份原GitHub專案。解壓本更新包，直接將scripts、docs、tests與其餘檔案放入原專案根目錄，不要多包一層資料夾。本包不含data快取，不會覆蓋舊行情與交易紀錄。
2. 包含 `.github/workflows/update.yml`。Mac Finder可用Command+Shift+.顯示隱藏檔。若瀏覽器漏掉它，在GitHub開啟該路徑編輯並貼上本包內容。
3. **保留線上較新的 docs/data/history.json、ledger.json、signals_v2.json，不用包內快取覆蓋它們。** 建議只上傳 scripts、tests、docs/index.html、docs/app.js、docs/strategy-spec.md、README.md、STRATEGY_SPEC.md、strategy_config.json 與workflow。watchlist無須更動。
4. Settings → Pages → Build and deployment → Source 改成 **GitHub Actions**。本工作流產生資料後直接發布docs，不再依賴分支推送觸發Pages。
5. Settings → Actions → General → Workflow permissions設為Read and write permissions（若政策允許）。若github-pages環境有分支限制，需允許main。
6. Actions → Daily Taiwan Stock Signals → Run workflow，選main。首次自動補16個月歷史；勾bootstrap可強制重抓。
7. 等update與deploy都綠燈，再開原網站。應出現六策略篩選與research-v2.1；錯誤請看Actions紀錄。

週一至週五台灣17:30排程，可能延遲；休市不產生新日線。首次10檔×16個月會比舊版久。TWSE實際擷取與GitHub發布須在Actions驗證，本交付完成離線測試。

## 六策略

|代碼|規則|方向|
|---|---|---|
|S1|多頭MA20回測收回|多|
|S2|20日箱體＋均線壓縮＋放量突破|多|
|S3|已確認W底突破頸線|多|
|S4|箱底止跌至箱頂|多|
|S5|假跌破收復後下一日確認|多／高風險|
|S6|M右頭收黑轉弱|空／高風險|

S3修正：一倍W底型態目標搭配底部停損，原1.5R門檻無法合理成立，改獨立0.8R研究門檻，並非已驗證優勢。其餘複雜子型態仍待開發。

## 目前功能限制

- 快取每檔96根，少於250根。Actions初始化成功後才可能產生候選。
- STOCK_DAY為原始未還原日線，尚未接入除權息還原因子、歷史交易狀態及交易日曆校驗。因此型態命中也只顯示DATA_MISSING研究候選，可執行訊號固定0。這不是判斷市場沒有機會。
- 目前實作六策略辨識與前瞻觀察快照；要提供有效訊號與績效，還需校驗後行情、成本及完整撮合／持倉回測引擎。改config的execution_enabled不會繞過檢查或開始下單。
- 僅watchlist上市普通股，非全市場；未加入上櫃行情與XQ族群。
- S6沒有借券可得性，僅供空方觀察。V3.3分數只作背景。

## 資料保存

- docs/data/ledger.json原樣保留舊版次日收盤模擬，不沿用為六策略績效。
- docs/data/signals_v2.json首次線上更新才建立；保留觀察當時時間，不回填歷史冒充前瞻。
- latest.json由程式產生，不手動維護。
- legacy_v33.py只沿用背景分數；update.py不執行舊交易模型。

## 本機驗證

```
python -m unittest discover -s tests -v
python scripts/update.py --offline
node --check docs/app.js
node tests/test_ui.cjs
python -m http.server 8000 --directory docs
```

offline只用快取，不修改history、ledger及前瞻快照；會更新latest並標OFFLINE_CACHE。正常更新執行 `python scripts/update.py`。

測試涵蓋六策略正反例、pivot確認延遲、未來不改寫訊號、暖機／品質門檻、tick、介面篩選及文字跳脫。未完成真實行情回測與實際瀏覽器視覺檢查。

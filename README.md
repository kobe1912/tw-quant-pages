# 台股六策略＋族群研究站 · 永豐 Shioaji 版

版本research-v3-sinopac。六策略辨識保留，行情來源改為永豐金證券Shioaji SDK；339檔名單匹配股票、73個原始族群已接入。這是唯讀行情研究工具，不包含券商下單、實際持倉或帳戶查詢。

## 先設定新金鑰，再上傳更新包

先撤銷曾貼在對話中的金鑰並重建，不要在公開repo、issue或對話貼新Secret。

GitHub專案 → Settings → Secrets and variables → Actions → Repository secrets → New repository secret，建立：

| Name | Secret內容 |
|---|---|
| SINOPAC_API_KEY | 你重建的永豐API Key |
| SINOPAC_SECRET_KEY | 對應Secret Key |

這兩項是Secrets，不是一般Variables，也不是Environment protection設定。若找不到設定，需repo管理權限。金鑰權限以行情唯讀為原則；本程式不呼叫交易API。

## 更新上傳

1. 解壓本包，將內部檔案放到原tw-quant-pages根目錄，不要另包一層資料夾。本包不含docs/data，既有行情、ledger與先前快照不被覆蓋。
2. 上傳scripts、tests、docs中的程式與規格、watchlist.json、sector_memberships.json、strategy_config.json、requirements.txt、README.md、STRATEGY_SPEC.md、.gitignore。
3. 特別更新 `.github/workflows/update.yml`：在GitHub打開該路徑，按鉛筆，將本包同名檔內容完整取代。Windows檔案總管可顯示「隱藏的項目」，Mac用Command+Shift+.。
4. Settings → Pages → Source保持GitHub Actions。Actions工作流程權限需允許讀寫；github-pages環境允許main發布。
5. 提交後工作流程可能自動啟動，不要再修改同批檔案；若缺金鑰，它會明確失敗且不發布半成品。

## 建議先跑一次連線測試

Actions → Daily Taiwan Stock Signals → Run workflow → main：勾選connection_only，執行。

成功時會只顯示connection=OK、2330聚合日線筆數與order_calls=0。此模式不更動公開資料、不發布網頁。

若出現LOGIN_FAILED: ShioajiConnectionError，代表尚未連上券商；不是證明Key正確或錯誤。檢查API開通、簽署／權限、IP限制、服務時間與runner連線環境。程式不自動切換正式模式、不反覆登入、不嘗試下單完成券商測試。原先此環境實測登入就出現過此錯誤，GitHub連線仍需你實際驗證。

## 正式讀取與發布

確認連線後，再建立一個Run workflow：**不要勾connection_only**，max_requests先保持80。

- update通過後會存回新資料，deploy發布原GitHub Pages網址。
- 首次339檔需分批補齊，最多80個查詢範圍／次，每段最多30天；不是80檔。420天初始化約需14–15段／檔，可能需多次執行、跨多日。
- 每次查詢前檢查官方流量餘額，預留100MiB；不能因進度慢就連續重跑到券商額度耗盡。配額低時等恢復後再續跑，不強制重抓已完成區間。
- 每日排程台灣週一至五17:30執行一次，可能延遲。未初始化股票依上次嘗試時間輪替，不固定只更新前幾個族群。
- 首頁會顯示339檔、永豐Shioaji、暖機完成數、已取得行情數、查詢進度。缺資料會清楚標出。
- 工作流讀main最新版本，資料提交前fetch/rebase後最多3次一般push；不使用force。若同時改了程式或資料衝突，它會停止並要求新Run workflow，不覆蓋遠端資料。

## 資料檔案與口徑

|檔案|用途|
|---|---|
|docs/data/sinopac_history.json|永豐分鐘聚合日K快取|
|docs/data/sinopac_sync.json|各股票補齊游標及查詢狀態|
|docs/data/sinopac_signals.json|永豐來源前瞻觀察快照|
|docs/data/latest.json|公開網頁讀取的研究結果|
|原history.json、ledger.json、signals_v2.json|保留舊版，不拼接到永豐績效|

分鐘K只取09:00–13:30正常時段，日期按官方Python範例時戳處理。量的股／張倍率由成交金額與價格比值核對，不明即拒絕該段。這與原TWSE全日成交統計可能不同，不直接拼接。

所有股票來自當前名單，不是歷史成分表。2646修正為星宇航空；3454晶睿、6747亨泰光、6806森崴能源因官方終止資料排除；原分類關係仍保存。未分類原4檔也保留。

族群平均漲跌與MA20上方比例，僅在該族群所有啟用成員暖機足夠、行情日期相同時顯示。未補齊不排名，也不把缺資料當零報酬。

## 目前仍有的限制

- 改接永豐不代表已完成歷史回測或撮合引擎。績效頁保持尚未開始，不將舊模擬當新績效。
- 原始行情未完整校驗除權息、交易日曆、暫停交易與借券可得性，仍輸出研究候選，可執行訊號保持0。
- 即使暖機滿250根，也要確認最新日期及來源口徑。分鐘聚合時間、量倍率應在成功連線後先與券商畫面抽查。
- GitHub Actions為一次性收盤任務，GitHub Pages不直接連券商，不是常駐盤中推播站。
- 原始行情是否可公開再散布須依券商／交易所資料授權；本更新不代表取得額外資料再散布權限。

## 本機執行

Python3.12：
```
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/update.py --offline
node --check docs/app.js
node tests/test_ui.cjs
```
本機連線需在私密環境變數設定兩個Secret；不在終端命令或原始碼填入金鑰。本包沒有.env，也不會要求你傳交易憑證。

## 測試範圍

已驗證六策略正反例、pivot延遲、無未來資料改寫、缺資料門檻、30天切段、成交量倍率、分鐘聚合、補抓續跑、錯誤保留游標、缺金鑰停止、族群覆蓋與介面篩選。測試使用合成資料，不是實際行情績效。此環境未成功連上永豐，未完成GitHub部署與瀏覽器視覺驗證。

官方文件：
- https://sinotrade.github.io/tutor/login/
- https://sinotrade.github.io/tutor/market_data/historical/
- https://sinotrade.github.io/tutor/limit/

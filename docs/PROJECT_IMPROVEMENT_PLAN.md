# AZA-STT 改進企劃

狀態：T4 已落地，不要重做。T1、T3、T5 仍未做。不要再為行數拆檔。  
評估基準：2026-10-18 / `main`  
最後檢視：2026-10-18

## 結論

Devin 的建議有一些值得做，但報告沒有完整讀到當時版本。下面「現況證據」才是目前程式。不能把這份報告當成待辦清單整包實作。

真正值得投入的方向只有三個：

1. 加入 Windows CI 與最短開發說明。
2. 先補齊 Groq 重試／錯誤分類測試，再從 `GroqDictateApp` 抽出一個深的 `GroqTranscriber` module。
3. 研究 Windows Credential Manager 是否值得取代目前的 ACL 設定檔；先做決策，不預設一定導入。

不要因為 `groq_dictate.py` 有 2347 行，就直接拆成 `recorder.py`、`api_client.py`、`ui_manager.py`、`config_manager.py`。行數不是 seam。沒有清楚 interface 的四個檔案，只會把同一套狀態分散到更多地方。

## 現況證據

- `paste_target.py`：前景視窗與貼上。不認識 app。
- `transcription_errors.py`：錯誤分類、key／model 輪替、繁中可行動訊息、log 遮罩 API key。這取代了 T2／T4 的呼叫政策，沒有做成 `GroqTranscriber` class。
- `recording_session.py`：錄音長度與開麥結果。不接收 app，不呼叫 Tk。執行緒與 `root.after` 留在 `GroqDictateApp`。
- `groq_dictate.py`：仍包含 Windows 錄音執行緒、快捷鍵、通知區、設定 UI、FLAC 與上傳。FLAC 失敗回退 WAV 仍在 app，所以 T3 不算完成。
- `transcription_interpreter.py`：獨立且可直接測試的轉錄 module。不要跟結構整理混在一起改詞彙或輸出政策。
- API key 會驗證 `gsk_` 格式，儲存在 `%LOCALAPPDATA%\AZA-STT\dictate_settings.conf`，Windows 上會用 `icacls` 限制為目前使用者可讀。
- UI 錯誤只顯示 `status_detail`。不要再加一套與 `is_recording`／`is_processing_ui` 平行的 phase 旗標。

## 對 Devin 十點建議的判斷

| 項目 | 判斷 | 建議處理 |
| --- | --- | --- |
| 1. 架構與組織 | 部分成立 | 不做四檔大拆分。先凍結 Groq 呼叫行為，再只抽出一個 `GroqTranscriber` module。錄音、UI、設定等到有第二個明確改動理由再拆。 |
| 2. 錯誤處理 | 部分成立 | 已有 log、timeout、模型／key 輪替與 UI 錯誤狀態。值得補的是「哪些錯誤該重試」與可行動的使用者訊息；離線模式不做。 |
| 3. 安全性 | 多數已處理 | 已有 key 格式驗證、原子寫入與 ACL。Credential Manager 可研究；完整性檢查價值低，因為能改檔的人通常也能改程式。 |
 | 4. 測試覆蓋 | 判斷錯誤 | 已有 76 tests，測試已搬進 `tests/` 以符合組織需求。值得新增 Groq retry／錯誤分類 mock tests 與 CI。 |
| 5. 效能 | 缺乏證據 | OpenCC 已快取，FLAC 只處理長錄音且在背景執行。沒有量測前不改；先保留目前設計。 |
| 6. 使用者體驗 | 少量值得做 | 已有狀態燈與通知區狀態。可改善錯誤訊息與解決方式；不加入使用統計、遙測或更多沒有實際需求的設定。 |
| 7. 可維護／擴展 | 大多過度設計 | 常數與設定正規化已集中。只有 Groq 一個 provider，不做 provider interface、插件系統或環境變數設定框架。 |
| 8. 文件與 DX | 小改值得做 | README 增加 Python 3.10、安裝依賴、跑測試、打包四條命令。外部貢獻出現前不新增 CONTRIBUTING、Sphinx 或 API 文件站。 |
| 9. 跨平台 | 不做 | 產品定位就是 Windows 桌面語音輸入，快捷鍵、剪貼簿、通知區與 Credential Manager 都是 Windows 工作。macOS／Linux 應另開專案。 |
| 10. 發布與部署 | 部分值得做 | 先加 Windows CI 跑測試。自動建 Release、auto-update 與 package manager 等有穩定發布需求後再做。 |

## 建議執行順序

每張票獨立 branch、獨立 commit。不要把結構搬移、提示詞、詞彙與輸出政策混在同一張票。

### T1：Windows CI 與開發說明

Outcome：每次 push／PR 都能在 Windows、Python 3.10 驗證目前測試；新 agent 不必猜開發命令。

Surface：

- 新增 `.github/workflows/test.yml`。
- 在 README 增加短的「開發與驗證」段落。
- 不改 runtime 程式碼。

Proof：

 - CI 執行 `python -m py_compile src/groq_dictate.py src/transcription_interpreter.py tests/test_groq_dictate.py tests/test_transcription_interpreter.py`。
 - CI 執行 `python -m unittest -q` 從專案根目錄。
- Windows runner 通過，且本機相同命令通過。

Stop：不要在這張票加入自動 Release、簽章、安裝器、coverage gate 或多版本 Python matrix。

### T2：凍結 Groq 呼叫與重試行為

Outcome：在搬動程式碼前，先用 public behaviour tests 鎖住現況。

Surface：

- 為 `transcribe_audio()` 加入 mock tests。
- 覆蓋成功、timeout、模型輪替、API key 輪替、全部失敗、FLAC 失敗後回退 WAV。
- 測試 observable outcome，不檢查私有欄位以外的內部步驟。

Proof：

- 測試能證明每個 model／key 的嘗試順序與上限。
- 測試能證明失敗不會遺留暫存 FLAC。
- 現有 76 tests 全部保留並通過。

Stop：這張票只加 regression tests，不改 retry policy，不移動 module。

### T3：抽出深的 GroqTranscriber module

Outcome：讓 UI／錄音流程只知道「送出音訊，取得 Groq verbose transcription」，不用知道 model、key 輪替、timeout 與 Groq client 建立方式。

建議 interface：

```python
transcriber = GroqTranscriber(api_keys, client_factory=Groq, sleep=time.sleep)
response = transcriber.transcribe(audio_path, prompt)
```

Surface：

- 新增 `groq_transcriber.py`。
- 從 `GroqDictateApp` 移出 Groq client 建立、model／key 輪替與遠端呼叫。
- `process_audio_workflow()`、錄音、UI、貼上、提示詞與文字政策保持原位。
- 原 T2 測試改從新 module 的 interface 驗證；不要保留一套重複測試舊實作。

Proof：

- T2 行為全部不變。
- `GroqDictateApp` 不再直接建立或輪替 Groq client。
- 完整 tests、`--self-test-language` 與新 EXE smoke test 通過。

Stop：不要順便建立 `SpeechProvider` base class、OpenAI／Azure adapter、插件 loader 或依賴注入框架。現在只有一個 provider；一個 hypothetical interface 沒有價值。

### T4：改善 retry policy 與錯誤訊息

Outcome：暫時性網路錯誤合理重試；永久錯誤快速失敗；使用者知道下一步能做什麼。

Surface：

- 先確認目前 Groq SDK 1.0.0 的實際 exception 類型與官方定義。
- timeout、429、5xx 才做有上限的退避；401／403 可切換下一把 key；格式或請求錯誤不要盲目重試所有組合。
- 對 UI 回傳少量穩定錯誤類別，例如「網路逾時」「API key 無效」「額度／速率限制」「服務暫時不可用」。詳細 exception 留在 log。
- dictation 重視延遲，退避必須有短上限；不要套用長時間的通用 server retry 套件。

Proof：

- 每種錯誤類別都有 deterministic mock test。
- 不在 log 或 UI 顯示 API key。
- 全部失敗時只出現一個可行動的最終訊息。

Stop：不做離線模型、不下載 Whisper、不加入背景工作佇列。

### T5：Credential Manager 決策與可選實作

Outcome：先回答「安全收益是否值得增加 Windows credential migration 與 recovery 複雜度」。

第一階段只交付一頁決策紀錄：

- 威脅模型：防止同帳號下的一般檔案誤讀，不宣稱能防止已控制使用者 session 的惡意程式。
- 比較目前 ACL 檔案與 Windows Credential Manager 的收益、相依性、PyInstaller 相容性、備份／遷移／刪除流程。
- 用一個 throwaway spike 證明 packaged EXE 能存、讀、刪測試 credential；spike 不直接合併產品。

只有決策為「採用」時才開第二張實作票。實作必須先寫入 Credential Manager 並驗證成功，之後才能刪除舊 key 檔；失敗時不得造成使用者無法錄音。

Stop：不自製加密、不把解密金鑰硬編碼進 EXE、不加入無法復原的自動遷移。

## 暫不做

- `recorder.py`、`ui_manager.py`、`config_manager.py` 四檔一次拆完。
- 離線 Whisper 或本機備援模型。
- 多 provider／插件架構。
- macOS、Linux 支援。
- 使用統計、遙測、API 用量追蹤。
- 自動更新器、package manager、安裝器。
- Sphinx、完整 API 文件網站、全面補 type hints。
- 沒有 profiler 或實際慢案例前的記憶體／FLAC 優化。

## Agent 執行規則

1. 每次只做一張票；開始前讀 `AGENTS.md`。
2. 保留 provider raw transcription，不從 timestamp tokens 重建文字。
3. 結構重整先補 public-interface regression，再搬程式；不得同時改 prompt、詞彙或輸出政策。
4. 不修改或提交 `%LOCALAPPDATA%` 設定、API key、`dist/`、`build/`、`release/`。
5. 只暫存本票明確檔案，不使用 `git add .`。
6. 最低驗證：Python 3.10 `py_compile` 與 `python -m unittest -q`。封裝敏感改動另跑 fresh EXE 與相關 self-test。
7. 回報變更檔案、測試命令、exit code，以及任何 `NOT RUN` 項目。

## 完成定義

這份企劃不是要求全部實作。T4 已落地。剩下 T1，然後才考慮 T3；T5 先決策。不要重做錯誤分類，也不要為了行數再拆檔。

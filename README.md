# TS Program Info

MPEG-TSファイルから番組情報（SID、番組名、説明、放送時刻）を取得するツール。

## 概要

MPEG-TSファイルに含まれるSDT（Service Description Table）とEIT（Event Information Table）を解析して、以下の情報を抽出します：

- サービスID（SID）
- サービス名（チャンネル名）
- 番組タイトル
- 番組説明（短形式）
- 詳細情報（拡張形式: 出演者など）
- 放送開始・終了時刻

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/noshiket/tseit_trimmer
cd tseit_trimmer
```

### 2. 仮想環境の構築

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windowsの場合: .venv\Scripts\activate
```

### 3. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

## 必要な環境

- **Python 3.7以上**
- **依存ライブラリ**:
  - ariblib: ARIB STD-B24文字列デコード用

## 使用方法

### 基本的な使い方

```bash
python3 tseit_trimmer.py -i INPUT.ts [-o OUTPUT.json]
```

### オプション

#### 入出力

- `-i, --input`: 入力TSファイル（必須）
- `-o, --output`: 出力JSONファイル（オプション）

#### サービス（SID）フィルタリング

- デフォルト: メインサービス（PAT内で最初に出現したサービス）のみ表示
- `-s, --sid [SID番号]`: 特定のSIDのみ抽出
- `--all-services`: 全サービス（ワンセグ、臨時サービス含む）を抽出

#### 時刻フィルタリング

- `--offset [秒数]`: TOTから指定秒数後に放送している番組のみ表示

#### その他

- `--all-events`: 全イベントを表示（デフォルトは最大5件）

## 使用例

### 1. メインサービスの番組情報を取得

```bash
python3 tseit_trimmer.py -i recording.ts
```

出力例：
```
Service Information:
  SID: 1024 (0x400)
  Service Name: サービス名
  Provider: プロバイダー名

Events (3):
  Event ID: 12345
  Start Time: 2025-01-01 19:00:00 JST
  End Time:   2025-01-01 19:30:00 JST
  Duration:   30 minutes
  Title: 番組タイトル
  Description: 番組の説明文
  Extended Info:
    番組内容: エピソードタイトルなど
```

### 2. JSON形式で出力

```bash
python3 tseit_trimmer.py -i recording.ts -o program_info.json
```

JSON出力例：
```json
{
  "ts_file": "recording.ts",
  "services": [
    {
      "sid": 1024,
      "service_name": "サービス名",
      "provider": "プロバイダー名",
      "events": [
        {
          "event_id": 12345,
          "start_time": "2025-01-01 19:00:00",
          "end_time": "2025-01-01 19:30:00",
          "duration_min": 30,
          "title": "番組タイトル",
          "description": "番組の説明文",
          "extended_info": "番組内容: ...\n出演者: ..."
        }
      ]
    }
  ]
}
```

### 3. 特定のSIDを指定

```bash
python3 tseit_trimmer.py -i recording.ts -s 1456
```

### 4. 全サービスを取得

```bash
python3 tseit_trimmer.py -i recording.ts --all-services
```

メインチャンネル、マルチビュー、ワンセグなど全てのサービスを表示します。

### 5. TOTからのオフセット時刻で番組を検索

```bash
python3 tseit_trimmer.py -i recording.ts --offset 30
```

TSファイルの最初のTOT（Time Offset Table）から30秒後に放送している番組のみを表示します。

出力例：
```
Searching for first TOT to calculate target time (offset: 30 seconds)...
  First TOT: 2025-01-01 19:00:00 JST
  Target time (TOT + 30s): 2025-01-01 19:00:30 JST

Service Information:
  SID: 1024 (0x400)
  Service Name: サービス名
  Provider: プロバイダー名

Events (1):
  Event ID: 12345
  Start Time: 2025-01-01 19:00:00 JST
  End Time:   2025-01-01 19:30:00 JST
  Duration:   30 minutes
  Title: 番組タイトル
  ...
```

## 技術詳細

### 解析対象

- **PAT（Program Association Table）**: サービスID一覧と順序
- **SDT（Service Description Table）**: サービス名、プロバイダー名
- **EIT（Event Information Table）**: イベント情報
  - 短形式イベント記述子（0x4D）: タイトル、簡潔な説明
  - 拡張形式イベント記述子（0x4E）: 詳細情報
- **TOT（Time Offset Table）**: 正確な放送時刻

### サービス選択の仕組み

デフォルトでは、PAT（Program Association Table）内で最初に出現したサービスを「メインサービス」として選択します。これにより、`ffprobe`などの他のツールと同じサービスが選択されます。

### ARIB文字列デコード

ARIB STD-B24で規定された文字列を`ariblib`ライブラリを使用してデコードします。エスケープシーケンスや制御コードも適切に処理されます。

### 重複除去

EITテーブルには同じイベントが複数回含まれることがあるため、event_idでユニーク化して重複を除去します。

## 出力フィールド

### サービス情報

- `sid`: サービスID
- `service_name`: サービス名（チャンネル名）
- `provider`: プロバイダー名

### イベント情報

- `event_id`: イベントID
- `start_time`: 開始時刻（JST）
- `end_time`: 終了時刻（JST）
- `duration_min`: 放送時間（分）
- `title`: 番組タイトル
- `description`: 短形式の番組説明
- `extended_info`: 拡張形式の詳細情報

## 注意点

- TSファイルに含まれるSDT/EITテーブルの情報を解析するため、ファイルによっては情報が不完全な場合があります
- デフォルトでは最大100万パケットをスキャンします
- イベント表示は最大5件ですが、JSON出力には全件含まれます

## ライセンス
MIT Licenseです。
LICENSEファイルに記載してます。

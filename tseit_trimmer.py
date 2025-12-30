#!/usr/bin/env python3
"""
TS Program Info - TSファイルから番組情報（SID、番組名、説明、放送時刻）を取得

使用方法:
python3 tseit_trimmer.py -i test.ts [-o test.eit.json] [--all-events] [--all-services] [--offset n(nは秒時間))]
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import argparse
import sys
import json
import ariblib.aribstr


# ==============================================================================
# Constants
# ==============================================================================

TS_PACKET_SIZE = 188
SYNC_BYTE = 0x47

PAT_PID = 0x00
SDT_PID = 0x11
EIT_PID = 0x12
EIT_H_PID = 0x26
EIT_M_PID = 0x27
TOT_PID = 0x14

PAT_TABLE_ID = 0x00
SDT_TABLE_ID = 0x42
EIT_PF_ACTUAL_TABLE_ID = 0x4E  # Present/Following
TOT_TABLE_ID = 0x73

# ジャンルコード（大分類）
ARIB_GENRE_LARGE = {
    0x0: "ニュース/報道",
    0x1: "スポーツ",
    0x2: "情報/ワイドショー",
    0x3: "ドラマ",
    0x4: "音楽",
    0x5: "バラエティ",
    0x6: "映画",
    0x7: "アニメ/特撮",
    0x8: "ドキュメンタリー/教養",
    0x9: "劇場/公演",
    0xA: "趣味/教育",
    0xB: "福祉",
    0xC: "予備",
    0xD: "予備",
    0xE: "拡張",
    0xF: "その他",
}

# コンポーネントタイプ（映像）
# stream_content = 0x01
COMPONENT_TYPE_VIDEO = {
    0x01: {"resolution": "480i (525i)", "aspect": "4:3", "pan_vector": False},
    0x02: {"resolution": "480i (525i)", "aspect": "16:9", "pan_vector": True},
    0x03: {"resolution": "480i (525i)", "aspect": "16:9", "pan_vector": False},
    0x04: {"resolution": "480i (525i)", "aspect": "> 16:9", "pan_vector": False},
    0x83: {"resolution": "4320p", "aspect": "16:9", "pan_vector": False},
    0x91: {"resolution": "2160p", "aspect": "16:9", "pan_vector": False},
    0x92: {"resolution": "2160p", "aspect": "16:9", "pan_vector": False},
    0x93: {"resolution": "2160p", "aspect": "16:9", "pan_vector": False},
    0x94: {"resolution": "2160p", "aspect": "16:9", "pan_vector": False},
    0xA1: {"resolution": "480p (525p)", "aspect": "4:3", "pan_vector": False},
    0xA2: {"resolution": "480p (525p)", "aspect": "16:9", "pan_vector": True},
    0xA3: {"resolution": "480p (525p)", "aspect": "16:9", "pan_vector": False},
    0xA4: {"resolution": "480p (525p)", "aspect": "> 16:9", "pan_vector": False},
    0xB1: {"resolution": "1080i (1125i)", "aspect": "4:3", "pan_vector": False},
    0xB2: {"resolution": "1080i (1125i)", "aspect": "16:9", "pan_vector": True},
    0xB3: {"resolution": "1080i (1125i)", "aspect": "16:9", "pan_vector": False},
    0xB4: {"resolution": "1080i (1125i)", "aspect": "> 16:9", "pan_vector": False},
    0xC1: {"resolution": "720p (750p)", "aspect": "4:3", "pan_vector": False},
    0xC2: {"resolution": "720p (750p)", "aspect": "16:9", "pan_vector": True},
    0xC3: {"resolution": "720p (750p)", "aspect": "16:9", "pan_vector": False},
    0xC4: {"resolution": "720p (750p)", "aspect": "> 16:9", "pan_vector": False},
    0xD1: {"resolution": "240p", "aspect": "4:3", "pan_vector": False},
    0xD2: {"resolution": "240p", "aspect": "16:9", "pan_vector": True},
    0xD3: {"resolution": "240p", "aspect": "16:9", "pan_vector": False},
    0xD4: {"resolution": "240p", "aspect": "> 16:9", "pan_vector": False},
    0xE1: {"resolution": "1080p (1125p)", "aspect": "4:3", "pan_vector": False},
    0xE2: {"resolution": "1080p (1125p)", "aspect": "16:9", "pan_vector": True},
    0xE3: {"resolution": "1080p (1125p)", "aspect": "16:9", "pan_vector": False},
    0xE4: {"resolution": "1080p (1125p)", "aspect": "> 16:9", "pan_vector": False},
    0xF1: {"resolution": "180p", "aspect": "4:3", "pan_vector": False},
    0xF2: {"resolution": "180p", "aspect": "16:9", "pan_vector": True},
    0xF3: {"resolution": "180p", "aspect": "16:9", "pan_vector": False},
    0xF4: {"resolution": "180p", "aspect": "> 16:9", "pan_vector": False},
}

# コンポーネントタイプ（音声）
# stream_content = 0x02
COMPONENT_TYPE_AUDIO = {
    0x01: {"mode": "1/0モード（シングルモノ）", "sampling": "48kHz", "quality": "モード1"},
    0x02: {"mode": "1/0モード（デュアルモノ）", "sampling": "48kHz", "quality": "モード1"},
    0x03: {"mode": "2/0モード（ステレオ）", "sampling": "48kHz", "quality": "モード1"},
    0x04: {"mode": "2/1モード", "sampling": "48kHz", "quality": "モード1"},
    0x05: {"mode": "3/0モード", "sampling": "48kHz", "quality": "モード1"},
    0x06: {"mode": "2/2モード", "sampling": "48kHz", "quality": "モード1"},
    0x07: {"mode": "3/1モード", "sampling": "48kHz", "quality": "モード1"},
    0x08: {"mode": "3/2モード", "sampling": "48kHz", "quality": "モード1"},
    0x09: {"mode": "3/2+LFEモード", "sampling": "48kHz", "quality": "モード1"},
    0x0A: {"mode": "3/3.1モード", "sampling": "48kHz", "quality": "モード1"},
    0x0B: {"mode": "2/0/0-2/0/2-0.1モード", "sampling": "48kHz", "quality": "モード1"},
    0x0C: {"mode": "5/2.1モード", "sampling": "48kHz", "quality": "モード1"},
    0x0D: {"mode": "3/2/2.1モード", "sampling": "48kHz", "quality": "モード1"},
    0x0E: {"mode": "2/0/0-3/0/2-0.1モード", "sampling": "48kHz", "quality": "モード1"},
    0x0F: {"mode": "0/2/0-3/0/2-0.1モード", "sampling": "48kHz", "quality": "モード1"},
    0x10: {"mode": "2/0/0-3/2/3-0.2モード", "sampling": "48kHz", "quality": "モード1"},
    0x11: {"mode": "3/3/3-5/2/3-3/0/0.2モード", "sampling": "48kHz", "quality": "モード1"},
    0x40: {"mode": "視覚障害者用音声解説", "sampling": "48kHz", "quality": "モード1"},
    0x41: {"mode": "聴覚障害者用音声", "sampling": "48kHz", "quality": "モード1"},
}

# ジャンルコード（中分類）
ARIB_GENRE_MIDDLE = {
    # 0x0: ニュース/報道
    0x00: {0x0: "定時・総合", 0x1: "天気", 0x2: "特集・ドキュメント", 0x3: "政治・国会",
           0x4: "経済・市況", 0x5: "海外・国際", 0x6: "解説", 0x7: "討論・会談",
           0x8: "報道特番", 0x9: "ローカル・地域", 0xA: "交通", 0xF: "その他"},
    # 0x1: スポーツ
    0x01: {0x0: "スポーツニュース", 0x1: "野球", 0x2: "サッカー", 0x3: "ゴルフ",
           0x4: "その他の球技", 0x5: "相撲・格闘技", 0x6: "オリンピック・国際大会",
           0x7: "マラソン・陸上・水泳", 0x8: "モータースポーツ", 0x9: "マリン・ウィンタースポーツ",
           0xA: "競馬・公営競技", 0xF: "その他"},
    # 0x2: 情報/ワイドショー
    0x02: {0x0: "芸能・ワイドショー", 0x1: "ファッション", 0x2: "暮らし・住まい", 0x3: "健康・医療",
           0x4: "ショッピング・通販", 0x5: "グルメ・料理", 0x6: "イベント", 0x7: "番組紹介・お知らせ",
           0xF: "その他"},
    # 0x3: ドラマ
    0x03: {0x0: "国内ドラマ", 0x1: "海外ドラマ", 0x2: "時代劇", 0xF: "その他"},
    # 0x4: 音楽
    0x04: {0x0: "国内ロック・ポップス", 0x1: "海外ロック・ポップス", 0x2: "クラシック・オペラ",
           0x3: "ジャズ・フュージョン", 0x4: "歌謡曲・演歌", 0x5: "ライブ・コンサート",
           0x6: "ランキング・リクエスト", 0x7: "カラオケ・のど自慢", 0x8: "民謡・邦楽",
           0x9: "童謡・キッズ", 0xA: "民族音楽・ワールドミュージック", 0xF: "その他"},
    # 0x5: バラエティ
    0x05: {0x0: "クイズ", 0x1: "ゲーム", 0x2: "トークバラエティ", 0x3: "お笑い・コメディ",
           0x4: "音楽バラエティ", 0x5: "旅バラエティ", 0x6: "料理バラエティ", 0xF: "その他"},
    # 0x6: 映画
    0x06: {0x0: "洋画", 0x1: "邦画", 0x2: "アニメ", 0xF: "その他"},
    # 0x7: アニメ/特撮
    0x07: {0x0: "国内アニメ", 0x1: "海外アニメ", 0x2: "特撮", 0xF: "その他"},
    # 0x8: ドキュメンタリー/教養
    0x08: {0x0: "社会・時事", 0x1: "歴史・紀行", 0x2: "自然・動物・環境", 0x3: "宇宙・科学・医学",
           0x4: "カルチャー・伝統文化", 0x5: "文学・文芸", 0x6: "スポーツ", 0x7: "ドキュメンタリー全般",
           0x8: "インタビュー・討論", 0xF: "その他"},
    # 0x9: 劇場/公演
    0x09: {0x0: "現代劇・新劇", 0x1: "ミュージカル", 0x2: "ダンス・バレエ", 0x3: "落語・演芸",
           0x4: "歌舞伎・古典", 0xF: "その他"},
    # 0xA: 趣味/教育
    0x0A: {0x0: "旅・釣り・アウトドア", 0x1: "園芸・ペット・手芸", 0x2: "音楽・美術・工芸",
           0x3: "囲碁・将棋", 0x4: "麻雀・パチンコ", 0x5: "車・オートバイ", 0x6: "コンピュータ・TVゲーム",
           0x7: "会話・語学", 0x8: "幼児・小学生", 0x9: "中学生・高校生", 0xA: "大学生・受験",
           0xB: "生涯教育・資格", 0xC: "教育問題", 0xF: "その他"},
    # 0xB: 福祉
    0x0B: {0x0: "高齢者", 0x1: "障害者", 0x2: "社会福祉", 0x3: "ボランティア", 0x4: "手話",
           0x5: "文字（字幕）", 0x6: "音声解説", 0xF: "その他"},
}


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class ServiceInfo:
    """サービス情報"""
    sid: int
    service_name: str
    provider_name: str
    events: List['EventInfo']


@dataclass
class EventInfo:
    """イベント（番組）情報"""
    event_id: int
    start_time: datetime
    duration_min: int
    title: str
    description: str
    extended_info: str
    genres: List[Dict[str, any]]  # [{"large_code": 0x0, "large_name": "ニュース/報道", ...}, ...]
    components: List[Dict[str, any]]  # [{"stream_content": 0x01, "component_type": 0xB0, "text": "1080i(1125i)"}, ...]


# ==============================================================================
# Utility Functions
# ==============================================================================

def bcd_to_decimal(bcd: int) -> int:
    """BCD（Binary Coded Decimal）を10進数に変換"""
    return ((bcd >> 4) * 10) + (bcd & 0x0F)


def mjd_to_datetime(mjd: int, hour_bcd: int, min_bcd: int, sec_bcd: int) -> Optional[datetime]:
    """
    MJD（Modified Julian Date）とBCD時刻をdatetimeに変換

    Args:
        mjd: Modified Julian Date
        hour_bcd, min_bcd, sec_bcd: BCD形式の時刻

    Returns:
        Optional[datetime]: JST時刻（ARIB規格ではJSTとして解釈）、変換失敗時はNone
    """
    # BCD to decimal
    hour = bcd_to_decimal(hour_bcd)
    minute = bcd_to_decimal(min_bcd)
    second = bcd_to_decimal(sec_bcd)

    # MJD to date (ETSI EN 300 468 Annex C)
    y_prime = int((mjd - 15078.2) / 365.25)
    m_prime = int((mjd - 14956.1 - int(y_prime * 365.25)) / 30.6001)
    day = mjd - 14956 - int(y_prime * 365.25) - int(m_prime * 30.6001)

    k = 1 if m_prime in (14, 15) else 0
    year = y_prime + k + 1900
    month = m_prime - 1 - k * 12

    try:
        # ARIB規格ではJSTとして記録されているため、そのまま返す
        jst_time = datetime(year, month, day, hour, minute, second)
        return jst_time
    except ValueError:
        return None


# ==============================================================================
# TSPacketUtil
# ==============================================================================

class TSPacketUtil:
    """MPEG-TS packet utility functions"""

    @staticmethod
    def get_pid(packet: bytes) -> int:
        """Extract PID from TS packet"""
        return ((packet[1] & 0x1F) << 8) | packet[2]

    @staticmethod
    def has_payload_start(packet: bytes) -> bool:
        """Check if packet has payload unit start indicator (PUSI)"""
        return (packet[1] & 0x40) != 0

    @staticmethod
    def has_adaptation_field(packet: bytes) -> bool:
        """Check if packet has adaptation field"""
        return (packet[3] & 0x20) != 0

    @staticmethod
    def get_payload_offset(packet: bytes) -> int:
        """Get payload offset in packet"""
        head_len = 4
        if TSPacketUtil.has_adaptation_field(packet):
            len_af = packet[4]
            head_len += 1 + len_af
        return head_len


# ==============================================================================
# ARIB String Decoder
# ==============================================================================

class ARIBStringDecoder:
    """ARIB STD-B24 文字列デコーダー（簡易版）"""

    @staticmethod
    def decode(data: bytes) -> str:
        """
        ARIB文字列をデコード

        Args:
            data: ARIB文字列バイト列

        Returns:
            str: デコードされた文字列
        """
        if not data:
            return ""

        # ariblibを使用してデコード
        try:
            text = ariblib.aribstr.AribString(data)
            return str(text).strip()
        except:
            pass

        # フォールバック: euc_jis_2004で試行
        try:
            text = data.decode('euc_jis_2004', errors='ignore')
            # 制御文字を削除
            text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t ')
            if text.strip():
                return text.strip()
        except:
            pass

        # 最終フォールバック: cp932で試行
        try:
            text = data.decode('cp932', errors='ignore')
            text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t ')
            return text.strip()
        except:
            return ""


# ==============================================================================
# Descriptor Parser
# ==============================================================================

class DescriptorParser:
    """ARIB記述子パーサー"""

    @staticmethod
    def parse_service_descriptor(data: bytes) -> tuple:
        """
        サービス記述子（0x48）をパース

        Args:
            data: 記述子データ

        Returns:
            tuple: (service_name, provider_name)
        """
        if len(data) < 3:
            return "", ""

        service_type = data[0]
        provider_name_length = data[1]

        offset = 2
        provider_name_bytes = data[offset:offset + provider_name_length]
        offset += provider_name_length

        if offset >= len(data):
            return "", ""

        service_name_length = data[offset]
        offset += 1
        service_name_bytes = data[offset:offset + service_name_length]

        provider_name = ARIBStringDecoder.decode(provider_name_bytes)
        service_name = ARIBStringDecoder.decode(service_name_bytes)

        return service_name, provider_name

    @staticmethod
    def parse_short_event_descriptor(data: bytes) -> tuple:
        """
        短形式イベント記述子（0x4D）をパース

        Args:
            data: 記述子データ

        Returns:
            tuple: (event_name, text)
        """
        if len(data) < 4:
            return "", ""

        # ISO_639_language_code (3 bytes)
        offset = 3

        event_name_length = data[offset]
        offset += 1
        event_name_bytes = data[offset:offset + event_name_length]
        offset += event_name_length

        if offset >= len(data):
            return "", ""

        text_length = data[offset]
        offset += 1
        text_bytes = data[offset:offset + text_length]

        event_name = ARIBStringDecoder.decode(event_name_bytes)
        text = ARIBStringDecoder.decode(text_bytes)

        return event_name, text

    @staticmethod
    def parse_extended_event_descriptor_raw(data: bytes) -> turple:
        if len(data) < 6:
            return b"", b""
        
        offset = 1 # descriptor_number
        offset += 3 # ISO_639_language_code
        # アイテム部の抽出
        item_len = data[offset]
        offset += 1
        item_bytes = data[offset:offset + item_len]
        offset += item_len
        
        # テキスト部の抽出
        text_len = data[offset] if offset < len(data) else 0
        offset += 1
        text_bytes = data[offset:offset + text_len] if text_len > 0 else b""

        # ここでは改行を挟まずに結合する
        return item_bytes, text_bytes

    @staticmethod
    def decode_combined_extended_info(item_payload: bytes, text_payload: bytes) -> str:
        """連結されたバイナリを解析し、アイテム名と本文を組み合わせて文字列にする"""
        results = []
        item_list = [] # [[name_bytes, content_bytes], ...]
        
        # 1. アイテム部の解析 (バイナリのまま項目ごとに集約)
        offset = 0
        while offset < len(item_payload):
            try:
                if offset >= len(item_payload): break
                name_len = item_payload[offset]
                offset += 1
                name_bytes = item_payload[offset:offset + name_len]
                offset += name_len
                
                if offset >= len(item_payload): break
                content_len = item_payload[offset]
                offset += 1
                content_bytes = item_payload[offset:offset + content_len]
                offset += content_len
                
                # 重要：名前長が0なら前の項目の続きとして結合する
                if name_len > 0 or not item_list:
                    item_list.append([name_bytes, content_bytes])
                else:
                    item_list[-1][1] += content_bytes
            except:
                break
                
        # 2. まとまったバイナリをデコード
        for n_b, c_b in item_list:
            n_str = ARIBStringDecoder.decode(n_b)
            c_str = ARIBStringDecoder.decode(c_b)
            if n_str:
                results.append(f"[{n_str}]\n{c_str}")
            else:
                results.append(c_str)
            
        # 3. テキスト部（番組説明の続きなど）のデコード
        if text_payload:
            t_str = ARIBStringDecoder.decode(text_payload)
            if t_str:
                results.append(t_str)
            
        return "\n".join(results)
    @staticmethod
    def parse_component_descriptor(data: bytes) -> Dict[str, any]:
        """
        コンポーネント記述子（0x50）をパース

        Args:
            data: 記述子データ

        Returns:
            Dict: コンポーネント情報 {"stream_content": 0x01, "component_type": 0xB3, "component_tag": 0x00, "language": "jpn", "text": "映像", "details": {...}}
        """
        if len(data) < 6:
            return {}

        stream_content = data[0] & 0x0F
        component_type = data[1]
        component_tag = data[2]

        # ISO_639_language_code (3 bytes)
        language_code = data[3:6].decode('ascii', errors='ignore')

        # Text
        text = ""
        if len(data) > 6:
            text_bytes = data[6:]
            text = ARIBStringDecoder.decode(text_bytes)

        # component_typeから詳細情報を取得
        details = {}
        if stream_content == 0x01:  # 映像
            if component_type in COMPONENT_TYPE_VIDEO:
                details = COMPONENT_TYPE_VIDEO[component_type].copy()
        elif stream_content == 0x02:  # 音声
            if component_type in COMPONENT_TYPE_AUDIO:
                details = COMPONENT_TYPE_AUDIO[component_type].copy()

        result = {
            "stream_content": stream_content,
            "component_type": component_type,
            "component_tag": component_tag,
            "language": language_code,
            "text": text
        }

        if details:
            result["details"] = details

        return result

    @staticmethod
    def parse_audio_component_descriptor(data: bytes) -> Dict[str, any]:
        if len(data) < 9:
            return {}

        stream_content = data[0] & 0x0F
        component_type = data[1]
        component_tag = data[2]
        stream_type = data[3]
        simulcast_group_tag = data[4]

        # フラグ
        ES_multi_lingual_flag = (data[5] & 0x80) != 0
        main_component_flag = (data[5] & 0x40) != 0
        quality_indicator = (data[5] & 0x30) >> 4
        sampling_rate = (data[5] & 0x0E) >> 1

        # 最初の言語コード (3 bytes)
        language_code = data[6:9].decode('ascii', errors='ignore')

        # 【修正】テキストの開始オフセットを計算
        offset = 9
        if ES_multi_lingual_flag:
            offset += 3 # 第二言語コードをスキップ

        # Text
        text = ""
        if len(data) > offset:
            text_bytes = data[offset:]
            text = ARIBStringDecoder.decode(text_bytes)

        # (以下、sampling_rate_map や details の処理はそのまま)
        sampling_rate_map = {
            0b001: "16kHz", 0b010: "22.05kHz", 0b011: "24kHz",
            0b101: "32kHz", 0b110: "44.1kHz", 0b111: "48kHz",
        }
        sampling_rate_text = sampling_rate_map.get(sampling_rate, "不明")

        details = {}
        if stream_content == 0x02:
            if component_type in COMPONENT_TYPE_AUDIO:
                details = COMPONENT_TYPE_AUDIO[component_type].copy()
                details["sampling"] = sampling_rate_text

        return {
            "stream_content": stream_content,
            "component_type": component_type,
            "component_tag": component_tag,
            "stream_type": stream_type,
            "language": language_code,
            "sampling_rate": sampling_rate_text,
            "main_component": main_component_flag,
            "text": text,
            "details": details
        }

    @staticmethod
    def parse_content_descriptor(data: bytes) -> List[Dict[str, any]]:
        """
        コンテンツ記述子（0x54）をパース

        Args:
            data: 記述子データ

        Returns:
            List[Dict]: ジャンル情報リスト [{"large_code": 0x0, "large_name": "ニュース/報道", "middle_code": 0x1, "middle_name": "天気"}, ...]
        """
        genres = []
        offset = 0

        while offset + 2 <= len(data):
            content_nibble_level_1 = (data[offset] >> 4) & 0x0F
            content_nibble_level_2 = data[offset] & 0x0F
            offset += 2

            # 大分類
            large_name = ARIB_GENRE_LARGE.get(content_nibble_level_1, "不明")

            # 中分類
            middle_name = None
            if content_nibble_level_1 in ARIB_GENRE_MIDDLE:
                middle_dict = ARIB_GENRE_MIDDLE[content_nibble_level_1]
                middle_name = middle_dict.get(content_nibble_level_2, "不明")

            genre_info = {
                "large_code": content_nibble_level_1,
                "large_name": large_name
            }

            if middle_name:
                genre_info["middle_code"] = content_nibble_level_2
                genre_info["middle_name"] = middle_name

            genres.append(genre_info)

        return genres


# ==============================================================================
# Table Parsers
# ==============================================================================

def parse_tot(packet: bytes) -> Optional[datetime]:
    """
    TOTパケットから時刻を抽出

    Args:
        packet: TSパケット

    Returns:
        Optional[datetime]: TOT時刻（JST）、パースできない場合None
    """
    if TSPacketUtil.get_pid(packet) != TOT_PID:
        return None

    if not TSPacketUtil.has_payload_start(packet):
        return None

    offset = TSPacketUtil.get_payload_offset(packet)
    if offset >= len(packet):
        return None

    # pointer_field
    pointer = packet[offset]
    offset += 1 + pointer

    if offset + 8 > len(packet):
        return None

    # table_id
    if packet[offset] != TOT_TABLE_ID:
        return None

    # MJD (Modified Julian Date) - 2 bytes
    mjd = (packet[offset + 3] << 8) | packet[offset + 4]

    # UTC time (BCD) - 3 bytes
    hour_bcd = packet[offset + 5]
    min_bcd = packet[offset + 6]
    sec_bcd = packet[offset + 7]

    return mjd_to_datetime(mjd, hour_bcd, min_bcd, sec_bcd)


def parse_pat_section(section_data: bytes) -> List[int]:
    """
    PATセクションをパースしてサービスIDのリストを返す（出現順）

    Args:
        section_data: セクションデータ

    Returns:
        List[int]: サービスIDのリスト（PAT内の出現順）
    """
    if len(section_data) < 8:
        return []

    service_ids = []

    # Skip to program loop (after header)
    offset = 8

    while offset + 4 <= len(section_data) - 4:  # -4 for CRC
        program_number = (section_data[offset] << 8) | section_data[offset + 1]
        # program_number 0 is Network PID, skip it
        if program_number != 0:
            service_ids.append(program_number)
        offset += 4

    return service_ids


class SDTParser:
    """SDT（Service Description Table）パーサー"""

    @staticmethod
    def parse_sdt_section(section_data: bytes) -> Dict[int, tuple]:
        """
        SDTセクションをパース

        Args:
            section_data: セクションデータ

        Returns:
            Dict[int, tuple]: {sid: (service_name, provider_name)}
        """
        if len(section_data) < 11:
            return {}

        services = {}

        # Skip to service loop
        offset = 11

        while offset + 5 <= len(section_data) - 4:  # -4 for CRC
            service_id = (section_data[offset] << 8) | section_data[offset + 1]
            descriptors_loop_length = ((section_data[offset + 3] & 0x0F) << 8) | section_data[offset + 4]

            offset += 5
            desc_end = offset + descriptors_loop_length

            service_name = ""
            provider_name = ""

            # Parse descriptors
            while offset + 2 <= desc_end:
                desc_tag = section_data[offset]
                desc_length = section_data[offset + 1]
                offset += 2

                if offset + desc_length > desc_end:
                    break

                if desc_tag == 0x48:  # Service descriptor
                    desc_data = section_data[offset:offset + desc_length]
                    service_name, provider_name = DescriptorParser.parse_service_descriptor(desc_data)

                offset += desc_length

            if service_name:
                services[service_id] = (service_name, provider_name)

            offset = desc_end

        return services


class EITParser:
    """EIT（Event Information Table）パーサー"""

    @staticmethod
    def parse_eit_section(section_data: bytes) -> List[tuple]:
        if len(section_data) < 14:
            return []

        events = []
        offset = 14

        while offset + 12 <= len(section_data) - 4:
            event_id = (section_data[offset] << 8) | section_data[offset + 1]

            # 開始時刻と放送時間の取得
            start_mjd = (section_data[offset + 2] << 8) | section_data[offset + 3]
            start_time = mjd_to_datetime(start_mjd, section_data[offset + 4], section_data[offset + 5], section_data[offset + 6])
            duration_bcd = section_data[offset + 7:offset + 10]
            duration_min = bcd_to_decimal(duration_bcd[0]) * 60 + bcd_to_decimal(duration_bcd[1])

            descriptors_loop_length = ((section_data[offset + 10] & 0x0F) << 8) | section_data[offset + 11]
            offset += 12
            desc_end = offset + descriptors_loop_length

            title = ""
            description = ""
            extended_dict = {}
            genres = []
            components = []
            ext_items_raw = {}
            ext_texts_raw = {}

            # 記述子ループ
            while offset + 2 <= desc_end:
                desc_tag = section_data[offset]
                desc_length = section_data[offset + 1]
                offset += 2
                desc_data = section_data[offset:offset + desc_length]

                if desc_tag == 0x4D:  # Short event
                    title, description = DescriptorParser.parse_short_event_descriptor(desc_data)
                elif desc_tag == 0x4E:  # Extended event
                    desc_num = (desc_data[0] >> 4) & 0x0F
                    i_b, t_b = DescriptorParser.parse_extended_event_descriptor_raw(desc_data)
                    ext_items_raw[desc_num] = i_b
                    ext_texts_raw[desc_num] = t_b
                elif desc_tag == 0x54:  # Content (Genre)
                    genres = DescriptorParser.parse_content_descriptor(desc_data)
                elif desc_tag == 0x50:  # Component (Video)
                    components.append(DescriptorParser.parse_component_descriptor(desc_data))
                elif desc_tag == 0xC4:  # Audio component
                    components.append(DescriptorParser.parse_audio_component_descriptor(desc_data))

                offset += desc_length
            # 全ての記述子ループが終わった後、連結して一括デコード
            combined_items = b"".join([ext_items_raw[k] for k in sorted(ext_items_raw.keys())])
            combined_texts = b"".join([ext_texts_raw[k] for k in sorted(ext_texts_raw.keys())])
            # 複数の拡張形式イベント記述子を番号順に空文字で連結し、最後に前後の余白を削る
            extended_info = DescriptorParser.decode_combined_extended_info(combined_items, combined_texts)

            events.append((event_id, start_time, duration_min, title, description, extended_info, genres, components))
            offset = desc_end

        return events


# ==============================================================================
# Section Collector
# ==============================================================================

class SectionCollector:
    """PSI/SIセクション収集（修正版：多重化対応・全セクション抽出）"""

    def __init__(self):
        # PIDとtable_idの組み合わせでバッファを分けることで混信を防ぐ
        self.buffers: Dict[tuple, bytearray] = {}

    def add_packet(self, packet: bytes) -> List[bytes]:
        pid = TSPacketUtil.get_pid(packet)
        offset = TSPacketUtil.get_payload_offset(packet)
        if offset >= len(packet):
            return []

        payload = packet[offset:]
        has_start = TSPacketUtil.has_payload_start(packet)
        complete_sections = []

        if has_start:
            # 1. 以前のパケットから続いていたセクションの「残り」を処理
            pointer_field = payload[0]
            if pointer_field > 0 and any(k[0] == pid for k in self.buffers):
                prefix = payload[1:1+pointer_field]
                for (p, tid), buf in self.buffers.items():
                    if p == pid and len(buf) > 0:
                        buf.extend(prefix)
                        self._extract_from_buffer((p, tid), complete_sections)

            # 2. 新しいセクションの開始処理
            new_section_data = payload[1+pointer_field:]
            if len(new_section_data) >= 3:
                table_id = new_section_data[0]
                key = (pid, table_id)
                if key not in self.buffers:
                    self.buffers[key] = bytearray()
                self.buffers[key].extend(new_section_data)
                self._extract_from_buffer(key, complete_sections)
        else:
            # 3. 継続パケット：該当PIDの全アクティブバッファに追記
            for (p, tid), buf in self.buffers.items():
                if p == pid and len(buf) > 0:
                    buf.extend(payload)
                    self._extract_from_buffer((p, tid), complete_sections)
        
        return complete_sections

    def _extract_from_buffer(self, key, results):
        """バッファから完成しているセクションをすべて取り出す"""
        buf = self.buffers[key]
        while len(buf) >= 3:
            # セクション長の取得（ARIB共通：先頭から3バイト目まで）
            section_len = ((buf[1] & 0x0F) << 8) | buf[2]
            total_len = section_len + 3
            
            if len(buf) >= total_len:
                results.append(bytes(buf[:total_len]))
                del buf[:total_len] # 抽出した分を削除
                # パディング(0xFF)をスキップ
                while len(buf) > 0 and buf[0] == 0xFF:
                    del buf[0]
            else:
                break # まだデータが足りない


# ==============================================================================
# Main
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="TS Program Info - Extract program information from TS file"
    )
    parser.add_argument("-i", "--input", required=True, help="Input TS file")
    parser.add_argument("-o", "--output", help="Output JSON file (optional)")
    parser.add_argument("-s", "--sid", type=int, help="Service ID to extract (default: main service only)")
    parser.add_argument("--offset", type=int, help="Time offset in seconds from first TOT (show only event at that time)")
    parser.add_argument("--all-services", action="store_true", help="Extract all services including one-seg and temporary")
    parser.add_argument("--all-events", action="store_true", help="Show all events (not just current/next)")

    args = parser.parse_args()

    print(f"Analyzing TS file: {args.input}")
    print()

    pat_collector = SectionCollector()
    sdt_collector = SectionCollector()
    eit_collector = SectionCollector()

    service_id_order: List[int] = []  # PAT内のサービスID順序
    services = {}
    events_by_service: Dict[int, List[tuple]] = {}
    target_time: Optional[datetime] = None
    need_tot = args.offset is not None  # TOT検索が必要かどうか

    if need_tot:
        print(f"Searching for first TOT to calculate target time (offset: {args.offset} seconds)...")

       # TS file scan
    with open(args.input, 'rb') as f:
        packet_count = 0
        max_packets = 1000000  # 最大100万パケットスキャン
        tot_found = False  # TOTが見つかったかのフラグ

        while packet_count < max_packets:
            packet = f.read(TS_PACKET_SIZE)
            if len(packet) < TS_PACKET_SIZE:
                break

            if packet[0] != SYNC_BYTE:
                continue

            pid = TSPacketUtil.get_pid(packet)

            # TOT(--offset指定時のみ)
            if need_tot and not target_time:
                tot_time = parse_tot(packet)
                if tot_time:
                    target_time = tot_time + timedelta(seconds=args.offset)
                    print(f"  First TOT: {tot_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
                    print(f"  Target time (TOT + {args.offset}s): {target_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
                    print()
                    tot_found = True
                    # TOT発見後、コレクターをリセットして新たに収集開始
                    pat_collector = SectionCollector()
                    sdt_collector = SectionCollector()
                    eit_collector = SectionCollector()
                packet_count += 1
                continue  # TOT発見前は他のパケット処理をスキップ

            # --offset指定時は、TOT発見後のみPAT/SDT/EITを処理
            if need_tot and not tot_found:
                packet_count += 1
                continue

            # --- PAT 処理部分 ---
            if pid == PAT_PID:
                sections = pat_collector.add_packet(packet) # section -> sections (List)
                for section in sections: # ループを追加
                    if len(section) > 0 and section[0] == PAT_TABLE_ID:
                        if not service_id_order:
                            service_id_order = parse_pat_section(section)

            # --- SDT 処理部分 ---
            elif pid == SDT_PID:
                sections = sdt_collector.add_packet(packet) # section -> sections (List)
                for section in sections: # ループを追加
                    if len(section) > 0 and section[0] == SDT_TABLE_ID:
                        parsed_services = SDTParser.parse_sdt_section(section)
                        services.update(parsed_services)

            # --- EIT 処理部分 ---
            elif pid in [EIT_PID, EIT_H_PID, EIT_M_PID]:
                sections = eit_collector.add_packet(packet) # section -> sections (List)
                for section in sections: # ループを追加
                    if len(section) > 8:
                        table_id = section[0]
                        if args.all_events or need_tot or table_id == EIT_PF_ACTUAL_TABLE_ID:
                            service_id = (section[3] << 8) | section[4] # ここでエラーが消えます
                            parsed_events = EITParser.parse_eit_section(section)

                            if service_id not in events_by_service:
                                events_by_service[service_id] = []
                            events_by_service[service_id].extend(parsed_events)

            packet_count += 1

            # 早期終了条件
            # --offsetが指定されている場合はより多くスキャン（完全なEIT情報を探すため）
            early_exit_threshold = 200000 if need_tot else 50000
            if services and events_by_service and packet_count > early_exit_threshold:
                break

    # 結果表示
    if not services:
        print("No service information found.", file=sys.stderr)
        sys.exit(1)

    # TOTチェック（--offset指定時）
    if need_tot and not target_time:
        print("Error: TOT not found in TS file", file=sys.stderr)
        sys.exit(1)

    # サービスフィルタリング
    if args.sid:
        # 指定されたSIDのみ
        if args.sid not in services:
            print(f"Error: SID {args.sid} not found in TS file", file=sys.stderr)
            print(f"Available SIDs: {sorted(services.keys())}", file=sys.stderr)
            sys.exit(1)
        filtered_services = {args.sid: services[args.sid]}
    elif args.all_services:
        # 全サービス
        filtered_services = services
    else:
        # デフォルト: メインサービスのみ（PAT内で最初に出現したサービス）
        if service_id_order:
            # PATの順序で最初のサービスを選択
            main_sid = None
            for sid in service_id_order:
                if sid in services:
                    main_sid = sid
                    break
            if main_sid is None:
                main_sid = next(iter(services.keys()))
        else:
            # PATが見つからない場合はSDTの順序
            main_sid = next(iter(services.keys()))
        filtered_services = {main_sid: services[main_sid]}

    service_list = []

    for sid, (service_name, provider_name) in sorted(filtered_services.items()):
        print(f"Service Information:")
        print(f"  SID: {sid} (0x{sid:x})")
        print(f"  Service Name: {service_name}")
        print(f"  Provider: {provider_name}")
        print()

        events = events_by_service.get(sid, [])

        # 重複を除去（event_idでユニーク化）
        seen_event_ids = set()
        unique_events = []
        for event in events:
            event_id = event[0]
            if event_id not in seen_event_ids:
                seen_event_ids.add(event_id)
                unique_events.append(event)

        # --offsetが指定された場合、target_timeに放送しているイベントのみを抽出
        if target_time:
            filtered_events = []
            for event_id, start_time, duration_min, title, description, extended_info, genres, components in unique_events:
                end_time = start_time + timedelta(minutes=duration_min)
                # target_timeがイベントの放送時間内にあるか確認
                if start_time <= target_time < end_time:
                    filtered_events.append((event_id, start_time, duration_min, title, description, extended_info, genres, components))
            unique_events = filtered_events

        if unique_events:
            print(f"Events ({len(unique_events)}):")
            event_info_list = []

            for event_id, start_time, duration_min, title, description, extended_info, genres, components in unique_events[:5]:  # 最大5件表示
                end_time = start_time + timedelta(minutes=duration_min)
                print(f"  Event ID: {event_id}")
                print(f"  Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
                print(f"  End Time:   {end_time.strftime('%Y-%m-%d %H:%M:%S')} JST")
                print(f"  Duration:   {duration_min} minutes")
                print(f"  Title: {title}")
                if genres:
                    genre_parts = []
                    for g in genres:
                        if "middle_name" in g:
                            genre_parts.append(f"{g['large_name']} > {g['middle_name']}")
                        else:
                            genre_parts.append(g['large_name'])
                    genre_names = ", ".join(genre_parts)
                    print(f"  Genre: {genre_names}")
                if components:
                    print(f"  Components:")
                    for comp in components:
                        comp_info = comp.get('text', '') if comp.get('text') else "Unknown"
                        if 'details' in comp:
                            details = comp['details']
                            if 'resolution' in details:  # 映像
                                comp_info = f"{details['resolution']}, アスペクト比{details['aspect']}"
                                if details.get('pan_vector') is False:
                                    comp_info += ", パンベクトルなし"
                            elif 'mode' in details:  # 音声
                                comp_info = f"{details['mode']}, {comp.get('language', 'unknown')}, {details['sampling']}"
                        print(f"    - {comp_info}")
                if description:
                    print(f"  Description: {description}")
                if extended_info:
                    print(f"  Extended Info:")
                    for line in extended_info.split('\n'):
                        print(f"    {line}")
                print()

                event_info_list.append(EventInfo(
                    event_id=event_id,
                    start_time=start_time,
                    duration_min=duration_min,
                    title=title,
                    description=description,
                    extended_info=extended_info,
                    genres=genres,
                    components=components
                ))

            service_list.append(ServiceInfo(
                sid=sid,
                service_name=service_name,
                provider_name=provider_name,
                events=event_info_list
            ))
        else:
            print("  No events found.")
            print()

    # JSON出力
    if args.output:
        json_data = {
            "ts_file": args.input,
            "services": [
                {
                    "sid": svc.sid,
                    "service_name": svc.service_name,
                    "provider": svc.provider_name,
                    "events": [
                        {
                            "event_id": evt.event_id,
                            "start_time": evt.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                            "end_time": (evt.start_time + timedelta(minutes=evt.duration_min)).strftime('%Y-%m-%d %H:%M:%S'),
                            "duration_min": evt.duration_min,
                            "title": evt.title,
                            "description": evt.description,
                            "extended_info": evt.extended_info,
                            "genres": evt.genres,
                            "components": evt.components
                        }
                        for evt in svc.events
                    ]
                }
                for svc in service_list
            ]
        }

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        print(f"JSON output written to: {args.output}")


if __name__ == "__main__":
    main()

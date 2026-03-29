#!/usr/bin/env python3
"""测试日志上传和 SSE 推送流程"""

import requests
import json
import time
import threading
import sys


def test_upload_logs():
    """测试 POST /logs/upload 接口"""
    print("\n" + "=" * 60)
    print("测试 1: POST /logs/upload")
    print("=" * 60)

    # 模拟日志数据
    logs = [
        {
            "action": "agent_fill",
            "app_context": "taobao",
            "resolution": "mask",
            "field": "phone_number",
            "agent_intent": "自动填入手机号",
            "pii_type": "PHONE_NUMBER",
            "relationship_tag": "本人",
            "rule_match": "phone-masking-v1",
            "quality_score": 4.5,
        },
        {
            "action": "share_or_send",
            "app_context": "wechat",
            "resolution": "block",
            "field": "medical_record",
            "agent_intent": "准备分享病历截图",
            "pii_type": "MedicalRecord",
            "relationship_tag": "陌生人",
            "rule_match": "medical-record-block-v1",
            "quality_score": 3.8,
            "minicpm_reasoning": "检测到病历截图，匹配规则：禁止向陌生人发送病历，已阻止",
        },
    ]

    try:
        resp = requests.post(
            "http://127.0.0.1:8001/logs/upload",
            json={"user_id": "test_win_user", "logs": logs},
            timeout=5,
        )
        print(f"状态码: {resp.status_code}")
        print(f"响应: {resp.json()}")

        if resp.status_code == 200:
            print("✅ 日志上传成功")
            return True
        else:
            print("❌ 日志上传失败")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器，请先启动 api_server.py")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_get_latest_logs():
    """测试 GET /logs/latest/{user_id} 接口"""
    print("\n" + "=" * 60)
    print("测试 2: GET /logs/latest/{user_id}")
    print("=" * 60)

    try:
        resp = requests.get(
            "http://127.0.0.1:8001/logs/latest/test_win_user",
            params={"limit": 5},
            timeout=5,
        )
        print(f"状态码: {resp.status_code}")
        data = resp.json()
        print(f"日志数量: {data.get('count', 0)}")

        if data.get("logs"):
            print("\n最新日志摘要:")
            for log in data["logs"][-2:]:
                print(f"  - {log.get('action')} -> {log.get('resolution')}")
                if "visual_summary" in log:
                    vs = log["visual_summary"]
                    print(f"    L2推理: {vs.get('l2_reasoning', {}).get('reasoning', 'N/A')}")

        if resp.status_code == 200:
            print("✅ 获取日志成功")
            return True
        else:
            print("❌ 获取日志失败")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_sse_stream():
    """测试 SSE /logs/stream/{user_id} 接口"""
    print("\n" + "=" * 60)
    print("测试 3: SSE /logs/stream/{user_id}")
    print("=" * 60)

    try:
        import sseclient
        import requests

        resp = requests.get(
            "http://127.0.0.1:8001/logs/stream/test_win_user",
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=10,
        )

        print(f"状态码: {resp.status_code}")

        client = sseclient.SSEClient(resp)
        print("等待服务器推送... (10秒)")

        start_time = time.time()
        received = 0

        for event in client.events():
            elapsed = time.time() - start_time
            print(f"[{elapsed:.1f}s] 收到事件: {event.event}")
            if event.data:
                data = json.loads(event.data)
                print(f"  数据: {json.dumps(data, ensure_ascii=False)[:200]}...")
            received += 1

            if elapsed > 10 or received >= 3:
                break

        print("✅ SSE 连接成功")
        return True

    except ImportError:
        print("⚠️ 跳过 SSE 测试 (需要安装 sseclient-py: pip install sseclient-py)")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        return False
    except Exception as e:
        print(f"❌ SSE 测试失败: {e}")
        return False


def test_windows_sdk():
    """测试 Windows SDK"""
    print("\n" + "=" * 60)
    print("测试 4: Windows SDK (telemetry_probe)")
    print("=" * 60)

    try:
        # 模拟 Windows SDK 的日志格式
        from windows_sdk.telemetry_probe import LogEntry, _config

        entry = LogEntry(
            action="agent_fill",
            app_context="taobao",
            resolution="mask",
            field="phone_number",
            agent_intent="自动填入手机号",
            pii_type="PHONE_NUMBER",
            quality_score=4.5,
        )

        print(f"生成的 event_id: {entry.event_id}")
        print(f"日志格式: {json.dumps(entry.to_dict(), ensure_ascii=False, indent=2)[:500]}...")

        print("✅ Windows SDK 测试成功")
        return True

    except Exception as e:
        print(f"❌ Windows SDK 测试失败: {e}")
        return False


def main():
    print("=" * 60)
    print("隐私代理日志系统测试")
    print("=" * 60)

    # 测试 Windows SDK
    sdk_ok = test_windows_sdk()

    # 测试 API 接口
    upload_ok = test_upload_logs()
    get_ok = test_get_latest_logs()
    sse_ok = test_sse_stream()

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"Windows SDK:    {'✅' if sdk_ok else '❌'}")
    print(f"日志上传:        {'✅' if upload_ok else '❌'}")
    print(f"获取日志:        {'✅' if get_ok else '❌'}")
    print(f"SSE 推送:        {'✅' if sse_ok else '❌'}")

    all_ok = sdk_ok and upload_ok and get_ok
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

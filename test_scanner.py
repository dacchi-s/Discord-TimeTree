"""単体テスト - TimeTree Automationを直接テスト"""
from config import config
from nlp_parser import NLPParser, Event
from timetree_automation import TimeTreeAutomation


def test_nlp_parser():
    """NLPパーサーのテスト"""
    print("=== Testing NLP Parser ===")

    parser = NLPParser()

    test_cases = [
        "明日の15時から会議",
        "来週の水曜日に終日で休み",
        "2026年2月14日の13時から2時間でバレンタインデー@東京タワー",
        # 複数日のテストケース
        "2月11日、15日、3月1日に出張",
        "来週の月曜日と水曜日に研修",
    ]

    for text in test_cases:
        print(f"\nInput: {text}")
        events = parser.parse(text)
        if events:
            print(f"  Found {len(events)} event(s):")
            for i, event in enumerate(events):
                print(f"  [{i+1}] Title: {event.title}")
                print(f"      Start: {event.start_time}")
                print(f"      End: {event.end_time}")
                print(f"      All Day: {event.all_day}")
                print(f"      Location: {event.location}")
        else:
            print("  Failed to parse")


def test_timetree_automation():
    """TimeTree Automationのテスト"""
    print("\n=== Testing TimeTree Automation ===")

    config.validate()

    # テスト用のEventオブジェクトを作成
    test_event = Event(
        title="テスト会議",
        start_time="2026-02-12T15:00:00+09:00",
        end_time=None,
        all_day=False
    )

    print(f"\nTest event: {test_event}")

    automation = TimeTreeAutomation(headless=True)  # headlessモードで実行
    success = automation.run(test_event)

    if success:
        print("\n✓ Test passed!")
    else:
        print("\n✗ Test failed!")


def interactive_mode():
    """対話モード - ユーザー入力を待って実行"""
    print("=== Interactive Mode ===")
    print("Enter natural language text to create event(s).")
    print("Type 'quit' to exit.\n")

    config.validate()
    parser = NLPParser()

    while True:
        text = input("> ").strip()

        if text.lower() in ["quit", "exit", "q"]:
            break

        if not text:
            continue

        # まずNLPパースを確認
        print("\nParsing event(s)...")
        events = parser.parse(text)

        if events:
            print(f"  Found {len(events)} event(s):")
            for i, event in enumerate(events):
                print(f"  [{i+1}] Title: {event.title}")
                print(f"      Start: {event.start_time}")
                print(f"      End: {event.end_time}")
                print(f"      All Day: {event.all_day}")
                print(f"      Location: {event.location}")

            confirm = input("\nCreate these event(s)? (y/n): ").strip().lower()
            if confirm == "y":
                created = 0
                for i, event in enumerate(events):
                    print(f"\n[{i+1}/{len(events)}] Creating: {event.title}...")
                    automation = TimeTreeAutomation(headless=True)  # headlessモードで実行
                    success = automation.run(event)

                    if success:
                        print("  ✓ Event created!")
                        created += 1
                    else:
                        print("  ✗ Failed to create event.")
                        print("  Stopping (remaining events will not be processed).")
                        break

                print(f"\nTotal: {created}/{len(events)} event(s) created.")
        else:
            print("Failed to parse event.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "nlp":
            test_nlp_parser()
        elif command == "full":
            test_timetree_automation()
        elif command == "scan":
            from selector_scanner import main as scan_main
            scan_main()
        else:
            print("Usage:")
            print("  python test_scanner.py nlp   - Test NLP parser")
            print("  python test_scanner.py full  - Test full automation")
            print("  python test_scanner.py scan  - Run UI scanner")
            print("  python test_scanner.py       - Interactive mode")
    else:
        interactive_mode()

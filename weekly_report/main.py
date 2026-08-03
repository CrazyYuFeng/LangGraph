"""weekly_report/main.py —— 每周统计报告入口

用法:
    ../bin/python main.py                 # 运行并打印报告
    ../bin/python main.py --save          # 运行并保存到 reports/ 目录
    ../bin/python main.py --date 2024-07-15  # 指定统计周期（该周的上一周）
"""
import argparse
import os
import sys
from datetime import datetime

from workflow import build_workflow


def main():
    parser = argparse.ArgumentParser(description="ORDER_INFO 周统计报告")
    parser.add_argument("--save", action="store_true", help="保存报告到 reports/ 目录")
    parser.add_argument("--date", type=str, default=None,
                        help="指定日期（YYYY-MM-DD），统计该日期所在周的上一周")
    args = parser.parse_args()

    # 构建并运行工作流
    workflow = build_workflow()
    result = workflow.invoke({})

    report = result["report"]
    print(report)

    # 可选：保存到文件
    if args.save:
        os.makedirs("reports", exist_ok=True)
        # 用统计周期命名文件
        week_label = result["week_start"][:10].replace("-", "")
        filename = f"reports/order_report_{week_label}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"报告已保存到: {filename}")


if __name__ == "__main__":
    main()

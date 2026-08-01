#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三轮：跑真正的 main()，看它**印出来的那一行**是什么。

不动仓库任何字节：把 va.KOTLIN_DTO 指向临时目录里的一份突变副本（运行时包装，D-322）。
这是给 v2 的那条结论唯一够强的证据形态——「check_one 返回空列表」是内部量，
「门印 OK」才是操作者看到的东西。
"""
import copy
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = r"E:\C Project\ANEB"
SPEC = os.path.join(ROOT, "spec", "adapters")
sys.path.insert(0, SPEC)
import validate_adapters as va  # noqa: E402

with open(va.KOTLIN_DTO, encoding="utf-8") as fh:
    KOTLIN = fh.read()
ANCHOR = '        @SerialName("caliber_redlines") val caliberRedlines: CaliberDto,'
REAL_KOTLIN_PATH = va.KOTLIN_DTO
REAL_HERE = va.HERE
REAL_ASSETS = va.ASSETS_DIR

STAMP = {"version_name": "1.2.3", "version_code": 1203,
         "captured_at": "2026-08-02", "source": "dumpsys package com.larus.nova",
         "ghost_key_a_strict_parser_would_reject": 1}

VSTAMP_SAME_FILE = ('\n@Serializable\ndata class VersionStampDto(\n'
                    '    @SerialName("version_name") val versionName: String,\n'
                    '    @SerialName("version_code") val versionCode: Int,\n'
                    '    @SerialName("captured_at") val capturedAt: String,\n'
                    '    val source: String,\n)\n')


def run_main(tag, kotlin_src, stamp_into_all_specs, note):
    """在临时沙箱里跑 main()：临时 spec 目录 + 临时 assets 镜像 + 临时 DTO 源。"""
    tmp = tempfile.mkdtemp(prefix="lensb3_")
    try:
        spec_dir = os.path.join(tmp, "spec_adapters")
        assets_dir = os.path.join(tmp, "assets")
        os.makedirs(spec_dir)
        os.makedirs(assets_dir)
        for name in sorted(f for f in os.listdir(REAL_HERE) if f.endswith(".json")):
            with open(os.path.join(REAL_HERE, name), encoding="utf-8") as fh:
                doc = json.load(fh)
            if stamp_into_all_specs is not None:
                doc["adapter"]["validated_against_version"] = copy.deepcopy(stamp_into_all_specs)
            raw = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
            with open(os.path.join(spec_dir, name), "wb") as fh:
                fh.write(raw)
            with open(os.path.join(assets_dir, name), "wb") as fh:   # 镜像逐字节一致
                fh.write(raw)
        kpath = os.path.join(tmp, "AdapterSpec.kt")
        with io.open(kpath, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(kotlin_src)

        va.KOTLIN_DTO, va.HERE, va.ASSETS_DIR = kpath, spec_dir, assets_dir
        va._DEFAULT_CONTRACT = None
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            rc = va.main()
        finally:
            sys.stdout = old
        print("=" * 78)
        print("[%s] %s" % (tag, note))
        print("  main() 退出码 = %d" % rc)
        for line in buf.getvalue().splitlines():
            print("  | %s" % line)
        return rc
    finally:
        va.KOTLIN_DTO, va.HERE, va.ASSETS_DIR = REAL_KOTLIN_PATH, REAL_HERE, REAL_ASSETS
        va._DEFAULT_CONTRACT = None
        shutil.rmtree(tmp, ignore_errors=True)


# 对照：完全不动 → 门必须绿（证明这个沙箱本身没坏）
run_main("CTRL", KOTLIN, None, "对照：未突变 + 未加版本戳 → 应 exit 0 且印 OK")

# 今天：DTO 没有该字段而 JSON 写了 → 必须红（这是 T11 ① 被阻塞的机器可判证据）
run_main("TODAY", KOTLIN, {"version_name": "1.2.3", "version_code": 1203,
                           "captured_at": "2026-08-02", "source": "dumpsys"},
         "今天：DTO 无该字段、JSON 写了 → 应 exit 1（A1 未知键）")

# 【给 v2 的那条】嵌套 DTO 声明在**别的文件** + 内部有一个严格解析器必拒的键
run_main("F1d", KOTLIN.replace(ANCHOR, ANCHOR + "\n"
                               '        @SerialName("validated_against_version")\n'
                               '        val validatedAgainstVersion: VersionStampDto? = null,'),
         STAMP,
         "【最要紧】VersionStampDto 在别的文件 + 内部含严格解析器必拒的键 → 门印什么？")

# 同一份 JSON，唯一差别是 DTO 声明在**同一个文件**里
run_main("F1d-ctrl", KOTLIN.replace(ANCHOR, ANCHOR + "\n"
                                    '        @SerialName("validated_against_version")\n'
                                    '        val validatedAgainstVersion: VersionStampDto? = null,')
         + VSTAMP_SAME_FILE,
         STAMP,
         "对照：唯一差别=DTO 挪回同文件 → 应 exit 1，逐份点名 ghost 键")

# v2 建议的正常落地形态（干净的版本戳，同文件 DTO，带默认值）
clean = {k: v for k, v in STAMP.items() if k != "ghost_key_a_strict_parser_would_reject"}
run_main("V2-good", KOTLIN.replace(ANCHOR, ANCHOR + "\n"
                                   '        @SerialName("validated_against_version")\n'
                                   '        val validatedAgainstVersion: VersionStampDto? = null,')
         + VSTAMP_SAME_FILE,
         clean, "v2 正常落地：同文件 data class + `= null` + 四份 JSON 都填干净版本戳 → 应 exit 0")

# 不带默认值 → 四份 JSON（此处未填戳）当场全红
run_main("V2-nodefault", KOTLIN.replace(ANCHOR, ANCHOR + "\n"
                                        '        @SerialName("validated_against_version")\n'
                                        '        val validatedAgainstVersion: VersionStampDto,')
         + VSTAMP_SAME_FILE,
         None, "v2 反面：字段**不带默认值**且 JSON 未填 → 应四份全红（A2）")

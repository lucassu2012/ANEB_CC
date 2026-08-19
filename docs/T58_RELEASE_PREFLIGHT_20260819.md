# T58 · release 构建预检报告（v2，2026-08-19）

> 大脑派单四小项的实测结果。**构建产物不入库**（`probe-release-unsigned.apk` 仅本地）。
> 全部结论由实跑命令产出，非推断。

---

## 摘要（一句话）

`assembleRelease` **当前失败**，唯一阻塞点＝**lintVital 拦下 `RadioCollector.kt:409` 的隐藏 API 反射**（`BlockedPrivateApi`）；**跳过 lintVital 后整条 release 链路跑通**（50.6 MB unsigned APK）。该反射**运行时行为无缺陷**（R-15 已有两级兜底），故这是**发布门问题、不是测量缺陷**。另有一处**必须在装机前拍板的真风险：release 变体不带 `networkSecurityConfig` → 连不上 E-01 bare-IP 自签通道**。

## ① `assembleRelease` 跑通性 + signing 现状

| 项 | 实测 |
|---|---|
| 直接 `assembleRelease` | ❌ **FAILED**：`:probe:lintVitalRelease` — `RadioCollector.kt:409 Reflective access to getNrState is forbidden when targeting API 35 and above [BlockedPrivateApi]`（1 error, 0 warnings） |
| `assembleRelease -x lintVitalRelease` | ✅ **BUILD SUCCESSFUL in 28s**（45 tasks，7 executed） |
| 产物 | `app/probe/build/outputs/apk/release/probe-release-unsigned.apk`，**50,587,185 B (≈50.6 MB)** |
| 签名 | ❌ **未签名**（`apksigner verify` → `DOES NOT VERIFY / Missing META-INF/MANIFEST.MF`）；`build.gradle.kts` release 块**无 `signingConfig`**（注释写明"阶段 1 前配置，自管 keystore、密钥不入库"） |
| 体积对比 | debug 61,125,332 B → release 50,587,185 B（**−17.2%**，仅来自不打 debug 符号；**非** R8 之功，见 ②） |

**待办（signing）**：装机验证前需建 keystore（**密钥与口令不入库**，走本地/环境变量），在 `release` 块接 `signingConfig`。当前 unsigned APK **无法直接安装**。

## ② R8 / minify 对反射·Room·序列化的影响

**当前 `isMinifyEnabled = false`**，`proguard-rules.pro` **无任何自定义规则**（全文件只有默认注释）。故：

- **现状＝零影响**：release 不混淆不裁剪，与 debug 同构。上表 −17.2% 体积差与 R8 无关。
- **若将来开启 R8，本项目有三处高危面**（提前登记，勿到时踩）：
  1. **反射**：`RadioCollector.readNrState` 走 `getDeclaredMethod("getNrState")` —— 类名/方法名字符串在混淆下不受影响（反射的是**平台类** `ServiceState`，不是本应用类），**安全**；但本应用内若将来新增自身类的反射需加 keep。
  2. **Room**：`@Entity/@Dao` 经 KSP 生成实现类，AGP 默认带 Room 的 consumer rules，**通常安全**；但 `AnebDatabase` 已到 **v20 且有 12 个 MigrationVxTest**，一旦混淆导致列名/类名错位，**迁移测试是唯一防线**——开 R8 那次必须全量跑 migration 测试。
  3. **序列化（已实查，非推断）**：项目用 `kotlinx.serialization`，但**两侧风险不同**——
     · **出口**（`engine/ResultReporter.kt` 上报/导出）走 `buildJsonObject { put("run", …) }`，**键名是字符串字面量** → 混淆**不影响**，✅ 安全；
     · **入口**（`adapter/AdapterSpec.kt` 等 `@Serializable`/`@SerialName` 数据类，严格模式解析 spec/profile）→ R8 会剥掉编译期生成的 serializer，**必须加 kotlinx-serialization 的 keep 规则**（官方 consumer rules 通常随依赖带入，但**开 R8 那次必须实测验证**：解析失败会表现为 profile 加载异常，而非静默）。
- **建议**：**本次发布不开 R8**（无收益、有风险；50 MB 体积主要是 Cronet 等原生库，R8 减不动）。作为独立议题另排。

## ③ 自签证书风险 ★ **必须拍板**（否则 release 装机即失败）

**实测事实**：
- `network_security_config.xml` **只存在于 `src/debug/res/xml/`**，且**只被 `src/debug/AndroidManifest.xml` 引用**（该 manifest 注释原文：*"release 不含 networkSecurityConfig，targetSdk>=28 默认禁明文"*）。
- 该配置承载**两个 domain-config**：
  - `10.0.2.2` / `127.0.0.1` — 明文 + 本地自签 CA `@raw/aneb_local_ca`（模拟器联调）
  - **`120.79.148.0`（E-01 bare-IP）— https + 自签 IP-SAN CA `@raw/aneb_ip_ca`**
- **后果**：release 变体**不信任 `aneb_ip_ca`** → 连 E-01 bare-IP 通道 **TLS 握手必失败**。而 bare-IP 正是 **SNI-RST 自动旁路的落点**（D-22/D-25：电信蜂窝对 sslip.io 主机名注入 RST，靠 bare-IP 通道采数）。**即：release 包在蜂窝下大概率测不了 E-01**。

**两案（供大脑拍板）**：

| 案 | 做法 | 优点 | 缺点 / 风险 |
|---|---|---|---|
| **A · 显式 anchor 进 release** | 把 NSC 移到 `src/main/`，release 保留 `120.79.148.0` 的 `<domain-config>` + `aneb_ip_ca` 锚（**去掉** 10.0.2.2/127.0.0.1 明文段） | E-01 bare-IP 在 release 可用；**测量能力与 debug 一致**（SNI-RST 旁路继续有效）；面收窄到单个 IP + 单个 CA | 发布物内含自签 CA 锚点：**仅对该 IP 生效**，不影响其它域名；需在报告里显式声明"该包信任一枚私有 CA（仅限 E-01 bare-IP）" |
| **B · debug-CA 白名单（维持现状）** | release 不带任何自签锚，E-01 只能走 sslip.io 公共证书通道 | 发布物零私有信任锚，最"干净" | **蜂窝下 SNI-RST 会让 E-01 直接不可达**（已实测：`sni=rst` 时旁路是唯一活路）→ **release 包在电信蜂窝上基本测不了**，与工具目的冲突 |

**我的建议＝案 A**（收窄版：只留 `120.79.148.0` + `aneb_ip_ca`，剔除明文段）。理由：私有锚**作用域被 domain-config 钉死在单个 IP**，安全面可控；而案 B 会让 release 丧失蜂窝主路径的测量能力——**发布一个测不了主场景的包，比带一枚受限私有锚风险更大**。请裁。

## ④ debug 残留清单

**`BuildConfig.DEBUG` 门控点共 9 处 / 4 文件**，逐条核对：

| 位置 | 内容 | release 行为 | 判定 |
|---|---|---|---|
| `adapter/AnebAccessibilityService.kt:313` | 事件级诊断日志（send-anchor v2） | `if (!BuildConfig.DEBUG) return` → **无输出** | ✅ 已门控 |
| `engine/ScenarioRunner.kt:125` · `engine/TestEngine.kt:86` | `/stream` 故障注入透传（C09 前置） | 上层门控 → **release 恒 null** | ✅ 已门控 |
| `ui/MainActivity.kt:169` `ab_netlog` · `:175` `inject` · `:176` `weaknet` | adb 自动化调试开关 | `BuildConfig.DEBUG &&` / `if (DEBUG)` → **release 全部失效** | ✅ 已门控 |
| `ui/MainActivity.kt:1157` | （同上模式的早退） | release 早退 | ✅ 已门控 |

- **D-479 隧道诊断日志**：全仓 `grep` **无 `D-479` 相关代码残留**；D-479 是"USB 隧道会导致测量失真"的**决策记录**（D-490 复述其教训），非代码开关。**无需处置**。
- **未发现**：硬编码测试端点、`Log.d` 裸打、`android:debuggable`（release 由 AGP 自动置 false）。

## 待办清单（发布前）

| # | 事项 | 阻塞级 | 属主建议 |
|---|---|---|---|
| 1 | **③ 自签证书两案拍板** | ⛔ **阻塞装机验证** | 大脑 |
| 2 | **① lintVital 阻塞处置**：三选一 —— (a) `@SuppressLint("BlockedPrivateApi")` 就地压制（**推荐**：行为已有兜底，且注释写明 R-15 语义）；(b) lint baseline 文件；(c) 该 lint 降级为 warning | ⛔ 阻塞出包 | 大脑拍板，v2 实施 |
| 3 | **签名配置**：建 keystore（密钥/口令不入库）+ release 块接 `signingConfig` | ⛔ 阻塞装机 | v2（需 PO 提供或授权自建 keystore） |
| 4 | R8 议题独立排期（本次不开） | 无 | 另排 |
| 5 | 装机验证（08-16 设备窗，大脑排） | — | 大脑排窗 |

## 附：两案的**确切改法**（已勘察，大脑一裁即可秒落地）

**lint 方案 (a)** —— 1 行改动：`radio/RadioCollector.kt:400` 现为 `@SuppressLint("MissingPermission")`，改为
```kotlin
@SuppressLint("MissingPermission", "BlockedPrivateApi") // R-15：反射失败已两级兜底（toString→nsa_unknown），非行为缺陷
```
该文件已 `import android.annotation.SuppressLint`，且同文件另有 3 处同款用法（`:237`/`:275`/`:400`），风格一致、零新增依赖。

**证书案 A** —— 移动 + 收窄：
- `src/debug/res/raw/aneb_ip_ca.pem` → `src/main/res/raw/`（`aneb_local_ca.pem` **留在 debug**，它只服务模拟器 10.0.2.2/127.0.0.1）
- `src/debug/res/xml/network_security_config.xml` → `src/main/res/xml/`，**只保留** `120.79.148.0` 那个 `domain-config`（`cleartextTrafficPermitted="false"` + `aneb_ip_ca` + `system` 双锚）；**明文段（10.0.2.2/127.0.0.1）留在 debug 版 NSC**（两份 NSC 各自 sourceSet，debug 覆盖 main）
- `src/main/AndroidManifest.xml` 的 `<application>` 加 `android:networkSecurityConfig="@xml/network_security_config"`
预计改动：2 个文件移动 + 1 份 debug NSC 瘦身 + 1 行 manifest 属性。**不碰任何 Kotlin 代码。**

## 附：复现命令

```
$env:JAVA_HOME='E:\tools\jdk-17.0.19+10'; $env:ANDROID_HOME='E:\tools\android-sdk'
cd 'E:\C Project\ANEB\app'
.\gradlew.bat :probe:assembleRelease --% -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897          # 复现 lint 失败
.\gradlew.bat :probe:assembleRelease -x lintVitalRelease --% -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897  # 跑通
```

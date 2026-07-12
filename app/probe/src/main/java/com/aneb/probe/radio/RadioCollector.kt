package com.aneb.probe.radio

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.telephony.CellInfo
import android.telephony.CellInfoLte
import android.telephony.CellInfoNr
import android.telephony.CellIdentityNr
import android.telephony.CellSignalStrengthNr
import android.telephony.TelephonyManager
import androidx.core.content.ContextCompat

/**
 * 阶段 0：一次性 TelephonyManager 快照（networkType / operator / 首个 LTE 或 NR 小区的
 * RSRP/SINR/PCI）。无权限时返回降级字符串而非抛异常（valid_low_confidence 语义，
 * 设计文档 §4.6：证据缺失≠隐式健康）。
 *
 * TODO(阶段1)：TelephonyCallback 1Hz + requestCellInfoUpdate 主动刷新 + CellInfo 自带
 * timestampNanos 对齐（R-02）；SubscriptionManager 绑定数据卡 subId（R-13）；
 * DisplayInfo/dataNetworkType/CellInfoNr.isRegistered 三元组制式判定（R-15）。
 */
class RadioCollector(private val context: Context) {

    fun snapshot(): String {
        val phoneStateOk = granted(Manifest.permission.READ_PHONE_STATE)
        val fineLocOk = granted(Manifest.permission.ACCESS_FINE_LOCATION)
        if (!phoneStateOk || !fineLocOk) {
            val missing = buildList {
                if (!phoneStateOk) add("READ_PHONE_STATE")
                if (!fineLocOk) add("ACCESS_FINE_LOCATION")
            }
            return "radio: permission denied (${missing.joinToString(",")}) -> valid_low_confidence"
        }
        val tm = context.getSystemService(TelephonyManager::class.java)
            ?: return "radio: TelephonyManager unavailable -> valid_low_confidence"
        return try {
            readSnapshot(tm)
        } catch (e: SecurityException) {
            // 双保险：个别 ROM 权限模型不一致
            "radio: SecurityException ${e.message} -> valid_low_confidence"
        }
    }

    @SuppressLint("MissingPermission") // 上方已显式检查两项权限
    private fun readSnapshot(tm: TelephonyManager): String {
        val networkType = networkTypeName(tm.dataNetworkType)
        val operator = tm.networkOperatorName?.takeIf { it.isNotBlank() } ?: "unknown"

        val cellInfos: List<CellInfo> = tm.allCellInfo ?: emptyList()
        val cellPart = describeFirstCell(cellInfos)

        return "radio: type=$networkType operator=$operator $cellPart"
    }

    private fun describeFirstCell(cellInfos: List<CellInfo>): String {
        // 定位服务总开关关闭时 allCellInfo 返回空（R-02 提示），显式区分于权限拒绝
        if (cellInfos.isEmpty()) return "cell=none (empty CellInfo; location service off or no coverage)"

        for (info in cellInfos) {
            when (info) {
                is CellInfoNr -> {
                    val sig = info.cellSignalStrength as? CellSignalStrengthNr
                    val id = info.cellIdentity as? CellIdentityNr
                    if (sig != null && id != null) {
                        return "cell=NR pci=${sanitize(id.pci)} ssRsrp=${sanitize(sig.ssRsrp)}dBm ssSinr=${sanitize(sig.ssSinr)}dB registered=${info.isRegistered}"
                    }
                }
                is CellInfoLte -> {
                    val sig = info.cellSignalStrength
                    val id = info.cellIdentity
                    return "cell=LTE pci=${sanitize(id.pci)} rsrp=${sanitize(sig.rsrp)}dBm rssnr=${sanitize(sig.rssnr)}dB registered=${info.isRegistered}"
                }
                else -> continue
            }
        }
        return "cell=no LTE/NR entry (${cellInfos.size} other cells)"
    }

    /** CellInfo 未知值哨兵（Integer.MAX_VALUE）转 "n/a"，防哨兵值混入数据（R-10 精神）。 */
    private fun sanitize(v: Int): String = if (v == Int.MAX_VALUE || v == Int.MIN_VALUE) "n/a" else v.toString()

    private fun granted(permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private fun networkTypeName(type: Int): String = when (type) {
        TelephonyManager.NETWORK_TYPE_NR -> "NR"
        TelephonyManager.NETWORK_TYPE_LTE -> "LTE"
        TelephonyManager.NETWORK_TYPE_HSPAP,
        TelephonyManager.NETWORK_TYPE_HSPA,
        TelephonyManager.NETWORK_TYPE_UMTS -> "3G"
        TelephonyManager.NETWORK_TYPE_UNKNOWN -> "unknown"
        else -> "other($type)"
    }
}

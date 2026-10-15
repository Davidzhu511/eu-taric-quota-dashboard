"""Generate English pages from the same UI source; fail on untranslated UI text."""
from pathlib import Path
import re
import sys

# Longer phrases are applied first. Numeric data and source URLs are unchanged.
PHRASES = '''
预估分摊税率仅为把已知待分配申请合并计算的情景估算\tThe blended duty estimate is a scenario using the known pending requests together
及看板情景估算不能替代具体产品的最终税率核定\tand dashboard scenarios do not replace the final duty assessment for the specific product
看板风险标签独立比较待分配申请与官方\tDashboard risk labels independently compare pending requests with the official
下一季度初始额度不等于届时实际余额\tThe next quarter's initial volume is not its actual opening balance
不是季度使用率或你这票货的最终税率\tnot quarterly utilisation or the final duty rate for your consignment
最后获得配额的申报被海关接受的日期\tDate of customs acceptance for the last declaration receiving quota
最早在报关接受后的第二个工作日处理\tare processed no earlier than the second working day after declaration acceptance
未用季度额度可在同一配额年度内结转\tUnused quarterly quota can be carried forward within the same quota year
进口须提供可核验的熔炼与浇铸国证明\tImports require verifiable evidence of the country of melt and pour
仅包含欧委会已收到但尚未分配的\tincludes only drawing requests received by the Commission but not yet allocated
前一季度的分配在季度结束后的第\tAllocation for the previous quarter stops on working day
历史数据不可用时不影响实时看板\tHistory failure does not affect the current dashboard
当前余额与待分配量仍属于本季度\tThe current balance and pending requests belong to this quarter
无待分配申请不表示新增进口免税\tNo pending requests does not imply duty-free treatment for new imports
未来余额未公布时不作零余额判断\tAn unpublished future balance is not treated as zero
该信息与非优惠原产地应分别核对\tVerify this information separately from non-preferential origin
余额为零时新增申请应按配额外\tWith zero balance, assess new requests at the out-of-quota rate of
因此页面可能低估实际在途申请\tThe page may therefore understate requests in transit
不同申报接受日期按先后分配\tRequests are allocated in declaration acceptance date order
官方最近一次分配的获配比例\tOfficial allocation ratio for the latest allocation
最终以海关实际获配结果为准\tThe actual customs allocation is authoritative
没有符合当前筛选条件的数据\tNo records match the current filters
不是欧委会处理分配的日期\tnot the Commission's allocation processing date
理论余额不是海关公布余额\tThe scenario balance is not the official customs balance
同日超额申请按比例分配\tOversubscribed requests for the same acceptance date are allocated pro rata
条规定本措施配额不视为\tprovides that quotas under this measure are not considered
只适用于该批有效申请\tapplies only to eligible requests in that batch
实际在途申请可能更多\tMore requests may be in transit
当前仍处于官方封锁期\tCurrently within the official blocking period
不是整个季度的税率\tThis is not a duty rate for the entire quarter
个欧委会工作日停止\tafter quarter-end on the Commission working-day calendar
已知申请后理论余额\tScenario balance after known requests
下列初始额度来自\tThese initial volumes come from
不代表申请压力低\tdoes not mean low application pressure
例如钢厂检验证书\tsuch as a mill test certificate
实际分配尚未完成\tActual allocation is not yet complete
点击编号核对原文\tClick the order number to verify the source
表示官方未提供\tmeans not provided by the official source
与熔炼浇铸证明\tand melt-and-pour evidence
未来有效期记录\tfuture validity-period records
存在处理时差\tprocessing has a time lag
地域字段不等同于所有非欧盟国家均有资格使用该池\tThe geographical field does not mean all non-EU countries are eligible for this pool
未来初始额度不等于届时实际可用余额\tFuture initial volume is not the actual available opening balance
前一季度申请窗口截至随后月份第\tThe application window for the previous quarter ends on working day
中国与其他适用来源共同使用\tChina shares this pool with other eligible origins
反补贴税在配额内仍可能征收\tcountervailing duties may still apply within quota
年度结束的未用量不再结转\tUnused volume at year-end is not carried forward
是本钢铁措施的配额外税率\tis the out-of-quota duty under this steel measure
未用额度在季度结束后的第\tUnused volume is carried forward on working day
结转后余额可超过初始额度\tAfter carryover, the balance may exceed the initial volume
初始额度不是累计使用率\tinitial volume is not cumulative utilisation
申请须提供全额税款担保\tApplications require security for the full duty amount
英国与欧盟数据完全分开\tSeparate UK and EU data
旧合同过渡豁免仅覆盖\tThe transitional exemption for old contracts only covers imports from
不能代表累计使用量\tdoes not represent cumulative utilisation
通知季度额度已分配\tdesignates a quota as Critical when
不能视为配额锁定\tThis does not secure a quota allocation
中国使用的共用池\tShared pool used by China
仅限同一配额年度\twithin the same quota year only
公开余额可能滞后\tPublished balances may lag
不代表已使用\tnot evidence of utilisation
个工作日结转\tafter quarter-end
实际分配数日\tactual allocations by several days
按源数据展示\tas published by the source
月起不再适用\tand is no longer applicable from October
适用的反倾销\tApplicable anti-dumping duties
须结合\tRefer to
及排除规则\tand exclusions
原产地依据英国法规\tOrigin eligibility follows UK legislation
仅覆盖英国\tCovers only UK
季度结转\tQuarterly carryover
临界状态与税率说明\tcritical status and duty guidance
英国季度规则\tUK quarterly rules
配额外与\toutside quota these are added to
结转使\tCarryover means that
余额占初始额度\tBalance as a share of initial volume
官方数据地域\tOfficial geographical area
立法原产地\tLegislative origin
封锁\tBlocking
暂停期与产品编码\tSuspension periods and commodity codes
官方已列出初始额度\tInitial volumes have been published
状态下余额尚未公布\tbalances are not yet published
初始额度与余额差\tInitial volume minus balance
搜索配额号或原产地\tSearch order number or origin
没有符合条件的数据\tNo matching records
英国钢铁\tUK steel
关税配额每日更新看板\tDaily tariff quota dashboard
配额看板\tQuota dashboard
欧盟看板\tEU dashboard
英国看板\tUK dashboard
英国立法文件\tUK legislation
官方数据集\tOfficial dataset
实施说明\tImplementation guidance
有效期未知\tUnknown validity period
余额尚未公布\tBalance not published
已过期\tExpired
未提供\tNot provided
不适用\tNot applicable
配额外税率\tOut-of-quota duty
五个编号\tfive order numbers
个工作日\tof the following month
日进口\timports
时指定为\t% of the quarterly volume has been allocated
累加\tcombined
共用池\tShared pool
英国\tUK
为\tis
个\trecords
关税配额数据看板\tTariff quota dashboard
钢铁关税配额每日更新看板\tDaily steel tariff quota dashboard
聚焦钢铁产品\tTracking steel categories
每日自动更新\tUpdated daily
官方来源\tOfficial source
官方数据日期\tOfficial data date
当前有效期\tCurrent validity period
最后检查\tLast checked
看板筛选与导出\tFilters and exports
全部\tAll
搜索\tSearch
或原产地\tor origin
排序\tSort
按类别排序\tCategory order
预估税率从高到低\tEstimated duty: high to low
待分配压力从高到低\tPending pressure: high to low
剩余比例从低到高\tRemaining share: low to high
历史数据\tHistorical snapshots
实时看板\tCurrent dashboard
导出\tExport
数据概览\tOverview
成功抓取\tSuccessfully fetched
所选范围\tSelected scope
待分配压力\tPending request pressure
为极高风险\tmeans very high risk
临界配额\tCritical quota
已耗尽\tExhausted
欧盟官方状态\tOfficial EU status
最高预估分摊税率\tHighest estimated blended duty
配额外比例\tOut-of-quota share
正在读取最新数据\tLoading latest data
当前规则\tCurrent rules
结转\tCarryover
展开查看\tExpand
正在加载\tLoading
配额数据\tquota data
本次未取得有效余额\tNo valid balance obtained this run
尚未生效\tNot yet effective
不在当前有效期\tOutside the current validity period
官方数值未提供\tOfficial numeric value unavailable
无待分配申请\tNo pending requests
下一季度\tNext quarter
官方预告\tOfficial preview
个编号\torder numbers
初始额度\tInitial volume
余额\tBalance
尚未公布\tNot yet published
官方记录的封锁期\tOfficial recorded blocking period
当前已结束\tEnded
需关注\tWatch
高风险\tHigh risk
极高风险\tVery high risk
当前配额余额\tCurrent quota balance
本次有\tThis run has
个编号未能更新\torder numbers that could not be updated
原产地\tOrigin
沿用上次数据\tPrevious data retained
初始配额\tInitial quota
待分配量\tPending requests
预估分摊税率\tEstimated blended duty
余额为零时新增申请\tNew requests with zero balance
配额外\tOut-of-quota
最近分配比例\tLatest allocation ratio
官方耗尽日期\tOfficial exhaustion date
临界配额状态\tCritical status
封锁期\tBlocking period
暂停期\tSuspension period
剩余比例\tRemaining share
剩余\tremaining
最近分配\tLatest allocation
数据加载失败\tData loading failed
历史\tHistory
官方\tOfficial
预计超量\tEstimated excess
数据版本\tDataset version
按配额号\tOrder number
从高到低\thigh to low
配额池\tquota pools
正在读取英国官方数据\tLoading official UK data
个编号未更新\torder numbers could not be updated
官方状态\tOfficial status
正在读取季度加权关税\tLoading quarterly weighted duty
评估\tassessment
否\tNo
是\tYes
年\t-
日至\tto
日起\tonwards
日\t
月\t-
条\tArticle
的\t
第\t
'''
MAPPING = dict(line.split('\t',1) for line in PHRASES.strip().splitlines() if '\t' in line)

MAPPING.update({
    '第': '', '日': '', '的': '',
    'CSV导出': 'Export CSV',
    'JSON导出': 'Export JSON',
    '058608剩余': '058608 remaining',
    '058608余额 / 初始额度': '058608 balance / initial volume',
    '季度结转、临界状态与税率说明': 'Quarterly carryover, critical status and duty guidance',
})

# Translate complete rule paragraphs to preserve natural English and legal meaning.
PARAGRAPHS = {
'2026 年 7 月 1 日至 2027 年 6 月 30 日，未用季度额度可在同一配额年度内结转。前一季度的分配在季度结束后的第 20 个欧委会工作日停止；下一季度初始额度不等于届时实际余额。': 'From 1 July 2026 to 30 June 2027, unused quarterly quota may be carried forward within the same quota year. Allocation for the previous quarter stops on the 20th Commission working day after quarter-end. The next quarter’s initial volume is not its actual opening balance.',
'2026/1457 第 5 条规定本措施配额不视为 Critical；官方「No」不代表申请压力低。看板风险标签独立比较待分配申请与官方 Balance，理论余额不是海关公布余额。': 'Article 5 of Regulation 2026/1457 provides that quotas under this measure are not considered Critical. An official “No” does not indicate low application pressure. Dashboard risk labels independently compare pending requests with the official balance; a scenario balance is not an official customs balance.',
'2026 年 10 月 1 日起，进口须提供可核验的熔炼与浇铸国证明，例如钢厂检验证书；该信息与非优惠原产地应分别核对。配额外 50% 及看板情景估算不能替代具体产品的最终税率核定。': 'From 1 October 2026, imports require verifiable evidence of the country of melt and pour, such as a mill test certificate. Check this separately from non-preferential origin. The 50% out-of-quota duty and dashboard scenarios do not replace the final duty assessment for a specific product.',
'Category 4 未用额度在季度结束后的第 20 个工作日结转，仅限同一配额年度；年度结束的未用量不再结转。前一季度申请窗口截至随后月份第 19 个工作日。': 'Unused Category 4 volume is carried forward on the 20th working day after quarter-end, within the same quota year only. Unused year-end volume is not carried forward. The previous quarter’s application window ends on the 19th working day of the following month.',
'旧合同过渡豁免仅覆盖 2026 年 7 月 1 日至 9 月 30 日进口，10 月起不再适用。HMRC 通知季度额度已分配 90% 时指定为 Critical，申请须提供全额税款担保。': 'The old-contract transitional exemption only covers imports from 1 July to 30 September 2026 and no longer applies from October. HMRC designates a quota Critical when notified that 90% of quarterly volume has been allocated. Applications then require security for the full duty amount.',
'50% 是本钢铁措施的配额外税率；适用的反倾销/反补贴税在配额内仍可能征收，配额外与 50% 累加。结转使「初始额度与余额差」不能代表累计使用量，官方 Fill rate 按源数据展示。': '50% is the out-of-quota duty under this steel measure. Applicable anti-dumping and countervailing duties may still apply within quota and are added to the 50% duty outside quota. Because of carryover, initial volume minus balance does not represent cumulative utilisation. Official fill rate is displayed as published.',
}

PARAGRAPHS.update({'Total awaiting allocation 仅包含欧委会已收到但尚未分配的 drawing requests；FCFS 存在处理时差，实际在途申请可能更多。预估分摊税率仅为把已知待分配申请合并计算的情景估算，不是整个季度的税率。不同申报接受日期按先后分配，同日超额申请按比例分配；最终以海关实际获配结果为准。无待分配申请不表示新增进口免税，余额为零时新增申请应按配额外 50% 评估。': 'Total awaiting allocation includes drawing requests received by the Commission but not yet allocated. FCFS processing has a lag and more requests may be in transit. The blended duty estimate combines known pending requests into a scenario; it is not a rate for the entire quarter. Requests are allocated in declaration acceptance date order, with oversubscribed requests for the same date allocated pro rata. The actual customs allocation is authoritative. No pending requests does not imply duty-free new imports; assess new requests at the 50% out-of-quota rate when the balance is zero.', '仅覆盖英国Category 4五个编号。余额 / 初始额度不是累计使用率；结转后余额可超过初始额度。原产地依据英国法规Table 4；公开余额可能滞后HMRC实际分配数日，不能视为配额锁定。': 'Covers the five UK Category 4 order numbers only. Balance divided by initial volume is not cumulative utilisation; carryover can increase the balance beyond the initial volume. Origin eligibility follows Table 4 of the UK legislation. Published balances may lag actual HMRC allocations by several days and do not secure quota availability.', '058608为Residual共用池，中国与其他适用来源共同使用；CSV地域字段不等同于所有非欧盟国家均有资格使用该池，须结合Table 4及排除规则。': '058608 is the Residual pool shared by China and other eligible origins. The CSV geographical field does not make every non-EU origin eligible. Check Table 4 and applicable exclusions. ', '最后获得配额的申报被海关接受的日期，不是欧委会处理分配的日期；—表示官方未提供': 'Customs acceptance date for the last declaration receiving quota, not the Commission processing date; — means not provided by the source', '官方最近一次分配的获配比例；只适用于该批有效申请，不是季度使用率或你这票货的最终税率': 'Official allocation ratio for the latest batch of eligible requests; not quarterly utilisation or the final duty rate for your consignment', '官方已列出初始额度；Future 状态下余额尚未公布，不代表已使用。未用额度在季度结束后的第 20 个工作日结转，未来初始额度不等于届时实际可用余额。': 'Initial volumes have been published. Future balances are not yet published and do not indicate utilisation. Unused volume is carried forward on the 20th working day after quarter-end. Future initial volume is not the actual available opening balance.', '聚焦钢铁产品 1A、2、4A、4B 的 55 个编号 · 每日自动更新': '55 steel quota order numbers across categories 1A, 2, 4A and 4B · Updated daily', '2026/1384 · 第 3、4、14 条': '2026/1384 · Articles 3, 4 and 14', '2026/1457 · 第 4、5 条': '2026/1457 · Articles 4 and 5', '英国钢铁Category 4关税配额每日更新看板': 'UK steel Category 4 daily tariff quota dashboard', '英国钢铁Category 4配额看板': 'UK steel Category 4 quota dashboard', 'Category 4配额池': 'Category 4 quota pools', '${r.length}个': '${r.length} records', '英国 · Category': 'UK · Category', '下列初始额度来自 TARIC 未来有效期记录。当前余额与待分配量仍属于本季度；未来余额未公布时不作零余额判断。点击编号核对原文。': 'These initial volumes come from future TARIC validity-period records. Current balances and pending requests belong to this quarter. An unpublished future balance is not zero. Click an order number to verify the source.'})

def translate(text):
    for zh,en in PARAGRAPHS.items():
        text=text.replace(zh,en)
    for zh in sorted(MAPPING, key=len, reverse=True):
        text=text.replace(zh,MAPPING[zh])
    text=text.replace('zh-CN','en-GB').replace('lang="en-GB"','lang="en"')
    text=text.replace('row.origin_zh||row.origin','row.origin')
    text=text.replace('x.origin_zh||x.origin','x.origin').replace('esc(x.origin_zh)','esc(x.origin)')
    # Chinese data is not translated with string substitution; use official English fields.
    text=text.replace('${m.warning||""}', 'Published balances may lag actual HMRC allocations by several days; they cannot secure quota availability.')
    text=text.replace('。','. ').replace('；','; ').replace('：',': ').replace('（','(').replace('）',')').replace('，',', ').replace('「','“').replace('」','”')
    missing=set(re.findall(r'[\u4e00-\u9fff]+',text))
    if missing:
        raise ValueError('Untranslated English UI: '+', '.join(sorted(missing)))
    return text


def main():
    site=Path(sys.argv[1])
    for source,dest in [('index.html','en.html'),('uk.html','uk-en.html')]:
        text=translate((site/source).read_text())
        text=text.replace('src="./shared-ui.js"','src="./shared-ui.js"')
        (site/dest).write_text(text)

if __name__=='__main__': main()

<template>
  <section class="page" :data-module="meta.key">
    <header class="page-head">
      <div>
        <h2>{{ meta.name }}</h2>
        <p class="page-desc">{{ meta.desc }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">
          登记{{ meta.entity }}
        </button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">
          导出{{ meta.name }}清单
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <QualityRuleLinksPanel v-if="meta.key === 'quality_rule'" />

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in meta.fields" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="String(row.id)">
          <tr :data-testid="`row-${row.id}`" :data-status="String(row.status)">
            <td v-for="column in meta.fields" :key="column">{{ row[column] ?? '—' }}</td>
            <td>{{ row.status }}</td>
            <td class="row-actions">
              <template v-if="meta.key === 'quality_result'">
                <button
                  class="link"
                  type="button"
                  :data-testid="`drilldown-${row.id}`"
                  @click="toggleDrilldown(row)"
                >
                  {{ expandedDrill === row.id ? '收起命中来源' : '命中来源 / 重检' }}
                </button>
                <button
                  class="link"
                  type="button"
                  :data-testid="`report-detail-${row.id}`"
                  @click="openDetail(row)"
                >
                  报告详情
                </button>
              </template>
              <button
                v-for="action in meta.actions"
                :key="action"
                class="link"
                type="button"
                :data-testid="`action-${row.id}-${action}`"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>

          <tr v-if="meta.key === 'quality_result' && expandedDrill === row.id" class="quality-extension-row">
            <td :colspan="meta.fields.length + 2">
              <div class="drill-panel" :data-testid="`drill-panel-${row.id}`">
                <p v-if="drillLoading" class="muted">正在按原报告身份读取实际命中…</p>
                <p v-else-if="drillError" class="error-text">{{ drillError }}</p>
                <template v-else-if="drill">
                  <div class="drill-head">
                    <div>
                      <h3>按命中维度钻取 · {{ drill.report.报告批次 }}</h3>
                      <p>
                        原检查批次：<strong>{{ drill.report.报告批次 }}</strong>；
                        实体：{{ drill.report.实体编码 }}；
                        报告轮次：{{ drill.report.报告轮次 || 'R1' }}
                      </p>
                      <p class="muted">{{ drill.report.summary }}</p>
                    </div>
                    <div class="drill-totals" data-testid="drill-totals">
                      <span>检查总数 {{ drill.totals.check_total }}</span>
                      <span>实际命中理由 {{ drill.totals.hit_count }}</span>
                      <span>受影响/待查行 {{ drill.totals.affected_record_count }}</span>
                    </div>
                  </div>

                  <div class="dimension-bar">
                    <span v-for="dim in drill.dimensions" :key="dim.dimension" class="dimension-chip">
                      {{ dim.dimension }}：{{ dim.hit_count }} 项 · {{ dim.standard_code }}
                    </span>
                  </div>

                  <div v-if="createResult?.ok" class="success-banner" data-testid="recheck-created">
                    <span>{{ createResult.message }}</span>
                    <RouterLink
                      class="btn primary"
                      :to="`/quality_recheck?batch=${createResult.batch.batch_code}`"
                    >
                      前往质量复查办理
                    </RouterLink>
                  </div>

                  <table class="data-table hit-table" data-testid="hit-source-table">
                    <thead>
                      <tr>
                        <th>勾选</th>
                        <th>实际命中记录 / 原行内容</th>
                        <th>命中维度与理由（可重检项）</th>
                        <th>重检预约</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="record in drill.records" :key="record.record_id" :data-testid="`hit-record-${record.record_id}`">
                        <td>
                          <input
                            type="checkbox"
                            :checked="isRecordSelected(record)"
                            :data-testid="`record-check-${record.record_id}`"
                            @change="toggleRecord(record)"
                          />
                        </td>
                        <td>
                          <strong>{{ record.record_label || record.record_id }}</strong>
                          <div class="muted">记录标识：{{ record.record_id }}</div>
                          <details open>
                            <summary>原行内容</summary>
                            <pre class="json-box">{{ JSON.stringify(record.original_row, null, 2) }}</pre>
                          </details>
                        </td>
                        <td>
                          <label
                            v-for="reason in record.reasons"
                            :key="reason.id"
                            class="reason-check"
                            :data-testid="`hit-item-${reason.id}`"
                          >
                            <input
                              type="checkbox"
                              :checked="isHitSelected(reason.id)"
                              :data-testid="`hit-check-${reason.id}`"
                              @change="toggleHit(reason.id)"
                            />
                            <span>
                              <span class="chip danger">{{ reason.dimension }}</span>
                              <strong>{{ reason.reason }}</strong>
                              <small>{{ reason.rule_standard }}</small>
                            </span>
                          </label>
                        </td>
                        <td>
                          <span v-if="record.scheduled" class="chip success">
                            已预约 {{ record.recheck_code }} / {{ record.recheck_status }}
                          </span>
                          <span v-else class="chip">尚未发起重检</span>
                          <p class="muted">同一记录多项理由只生成一笔重检。</p>
                        </td>
                      </tr>
                      <tr v-if="!drill.records.length">
                        <td colspan="4" class="empty-state">该报告没有可回查的实际命中来源</td>
                      </tr>
                    </tbody>
                  </table>

                  <div class="drill-actions">
                    <span data-testid="selected-summary">
                      已勾选 {{ selectedReasons.length }} 项理由，归并为 {{ selectedRecordCount }} 条重检记录
                    </span>
                    <button
                      class="btn primary"
                      type="button"
                      data-testid="open-recheck-confirm"
                      :disabled="!selectedReasons.length"
                      @click="confirmOpen = true"
                    >
                      勾选后办理 / 发起重检确认
                    </button>
                  </div>
                </template>
              </div>
            </td>
          </tr>
        </template>

        <tr v-if="!rows.length">
          <td :colspan="meta.fields.length + 2" class="empty-state">
            暂无{{ meta.name }}数据，可先登记{{ meta.entity }}
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记{{ meta.entity }}</h3>
        <label v-for="field in meta.fields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input v-model="createValues[field]" :data-testid="`create-${field}`" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="confirmOpen" class="modal-backdrop" data-testid="recheck-confirm-modal">
      <form class="modal" @submit.prevent="submitRecheck">
        <h3>重检确认</h3>
        <p>原报告：{{ drill?.report?.报告批次 }}</p>
        <p>
          本次勾选 <strong>{{ selectedReasons.length }}</strong> 项命中理由，
          按原报告身份和记录归并为 <strong>{{ selectedRecordCount }}</strong> 笔重检工作。
        </p>
        <ul class="confirm-list">
          <li v-for="record in selectedRecords" :key="record.record_id">
            记录 {{ record.record_label || record.record_id }}：
            {{ record.reasons.map((reason: any) => reason.dimension).join('、') }}
          </li>
        </ul>
        <p class="muted">服务端将保存原报告身份、实际输入和规则标准，生成可由规则重跑的清单。</p>
        <p v-if="actionError" class="error-text">{{ actionError }}</p>
        <div class="page-actions">
          <button class="btn" type="button" @click="confirmOpen = false">返回勾选</button>
          <button class="btn primary" type="submit" data-testid="submit-recheck" :disabled="submitting">
            {{ submitting ? '服务端确认中…' : '确认生成重检清单' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="detailOpen" class="modal-backdrop" data-testid="report-detail-modal" @click.self="detailOpen = false">
      <div class="modal wide-modal">
        <h3>报告详情：原命中与本次重检结果</h3>
        <p v-if="detailLoading" class="muted">读取中…</p>
        <p v-else-if="detailError" class="error-text">{{ detailError }}</p>
        <template v-else-if="detail">
          <p><strong>{{ detail.report.报告批次 }}</strong> · {{ detail.report.实体编码 }} · 轮次 {{ detail.report.报告轮次 || detail.report.round || 'R1' }}</p>

          <section>
            <h4>原报告命中原因</h4>
            <ul class="reason-list">
              <li v-for="hit in detail.original_hits" :key="hit.id" data-testid="detail-original-hit">
                <span class="chip danger">{{ hit.dimension }}</span>
                {{ hit.record_id }} · {{ hit.reason }}
                <div class="muted">{{ hit.rule_standard }}</div>
              </li>
            </ul>
          </section>

          <section>
            <h4>各轮检查结果与采用依据</h4>
            <article v-for="round in detail.rounds" :key="round.id" class="round-card" data-testid="report-round">
              <header>
                <strong>{{ round.报告批次 }}</strong>
                <span class="chip">{{ round.报告轮次 || round.round || 'R1' }}</span>
                <span>检查总数 {{ round.检查总数 }}；命中 {{ round.命中数 }}；评分 {{ round.评分结果 }}</span>
              </header>
              <p v-if="round.更正说明"><strong>更正说明：</strong>{{ round.更正说明 }}</p>
              <p v-if="round.使用规则标准"><strong>使用规则标准：</strong>{{ round.使用规则标准 }}</p>
              <p v-if="round.采用输入ID"><strong>采用输入：</strong>{{ round.采用输入ID }}</p>
              <ul v-if="round.本轮检查结果?.checks">
                <li v-for="check in round.本轮检查结果.checks" :key="check.rule_id">
                  {{ check.dimension }}：{{ check.result }}（实际值：{{ check.actual_value || '空' }}）
                </li>
              </ul>
            </article>
          </section>
        </template>
        <div class="page-actions">
          <button class="btn primary" type="button" @click="detailOpen = false">关闭</button>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ meta.name }}记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  createEntry,
  downloadEntries,
  listEntries,
  moduleMeta,
  runAction as applyAction,
} from '@/api/backend-service'
import { qualityGet, qualityPost, type QualityJson } from '@/api/quality'
import QualityRuleLinksPanel from '@/components/QualityRuleLinksPanel.vue'
import type { EntryRow } from '@/data/types'

const props = defineProps<{ moduleKey: string }>()
const route = useRoute()
const meta = moduleMeta(props.moduleKey)
const rows = ref<EntryRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = meta.fields.slice(0, 3)
const showCreate = ref(false)
const creating = ref(false)
const createValues = ref<Record<string, string>>({})
const stats = computed(() => [
  { label: meta.metrics[0], value: total.value },
  { label: meta.metrics[1], value: rows.value.filter((row) => row.status === meta.statuses[1]).length },
  {
    label: meta.metrics[2],
    value: rows.value.filter((row) => row.status === meta.statuses[meta.statuses.length - 1]).length,
  },
])
const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

const expandedDrill = ref<number | string | null>(null)
const drill = ref<QualityJson | null>(null)
const drillLoading = ref(false)
const drillError = ref('')
const selectedHitIds = ref<Array<number | string>>([])
const confirmOpen = ref(false)
const submitting = ref(false)
const actionError = ref('')
const createResult = ref<QualityJson | null>(null)
const detailOpen = ref(false)
const detail = ref<QualityJson | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const selectedReasons = computed<QualityJson[]>(() => {
  const sources = drill.value?.hit_sources || []
  const selected = new Set(selectedHitIds.value.map(String))
  return sources.filter((hit: QualityJson) => selected.has(String(hit.id)))
})
const selectedRecordCount = computed(() => new Set(selectedReasons.value.map((hit) => hit.record_id)).size)
const selectedRecords = computed(() => {
  const records = drill.value?.records || []
  const recordIds = new Set(selectedReasons.value.map((hit) => String(hit.record_id)))
  return records.filter((record: QualityJson) => recordIds.has(String(record.record_id)))
})

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    await downloadEntries(meta.key, filters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function openCreate() {
  createValues.value = Object.fromEntries(meta.fields.map((field) => [field, '']))
  errorMessage.value = ''
  showCreate.value = true
}

async function submitCreate() {
  creating.value = true
  errorMessage.value = ''
  try {
    const result = await createEntry(meta.key, createValues.value)
    if (!result.ok) throw new Error(result.message)
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  } finally {
    creating.value = false
  }
}

async function runAction(action: string, row: EntryRow) {
  errorMessage.value = ''
  try {
    const result = await applyAction(meta.key, Number(row.id), action)
    if (!result.ok) throw new Error(result.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await listEntries(meta.key, filters.value)
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '业务列表读取失败'
  }
}

async function loadDrilldown(rowId: number | string) {
  drillLoading.value = true
  drillError.value = ''
  drill.value = null
  try {
    drill.value = await qualityGet(`/api/quality_result/${rowId}/drilldown`)
  } catch (error) {
    drillError.value = error instanceof Error ? error.message : '命中来源读取失败'
  } finally {
    drillLoading.value = false
  }
}

async function toggleDrilldown(row: EntryRow) {
  createResult.value = null
  selectedHitIds.value = []
  if (expandedDrill.value === row.id) {
    expandedDrill.value = null
    drill.value = null
    return
  }
  expandedDrill.value = row.id
  await loadDrilldown(row.id)
}

function isHitSelected(id: number | string): boolean {
  return selectedHitIds.value.map(String).includes(String(id))
}

function toggleHit(id: number | string) {
  if (isHitSelected(id)) {
    selectedHitIds.value = selectedHitIds.value.filter((value) => String(value) !== String(id))
  } else {
    selectedHitIds.value = [...selectedHitIds.value, id]
  }
}

function isRecordSelected(record: QualityJson): boolean {
  const ids: Array<number | string> = record.reason_ids || []
  return ids.length > 0 && ids.every((id) => isHitSelected(id))
}

function toggleRecord(record: QualityJson) {
  const ids: Array<number | string> = record.reason_ids || []
  if (isRecordSelected(record)) {
    const idSet = new Set(ids.map(String))
    selectedHitIds.value = selectedHitIds.value.filter((id) => !idSet.has(String(id)))
  } else {
    const merged = [...selectedHitIds.value, ...ids]
    selectedHitIds.value = Array.from(new Set(merged.map(String)))
  }
}

async function submitRecheck() {
  if (!expandedDrill.value || !selectedHitIds.value.length) return
  submitting.value = true
  actionError.value = ''
  try {
    const result = await qualityPost(`/api/quality_result/${expandedDrill.value}/rechecks`, {
      hit_ids: selectedHitIds.value,
      reviewer: '复查员',
    })
    if (!result.ok) throw new Error(result.message || '重检清单生成失败')
    createResult.value = result
    confirmOpen.value = false
    selectedHitIds.value = []
    await loadDrilldown(expandedDrill.value)
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : '重检确认失败'
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: EntryRow) {
  detailOpen.value = true
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    detail.value = await qualityGet(`/api/quality_result/${row.id}/detail`)
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '报告详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

async function openDetailById(reportId: string) {
  detailOpen.value = true
  detailLoading.value = true
  try {
    detail.value = await qualityGet(`/api/quality_result/${reportId}/detail`)
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '报告详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  await reload()
  if (meta.key === 'quality_result' && route.query.report) {
    await openDetailById(String(route.query.report))
  }
})
</script>

<style scoped>
.quality-extension-row > td { background: #f8fafc; padding: 12px; }
.drill-panel { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
.drill-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.drill-head h3 { margin: 0 0 6px; }
.drill-head p { margin: 3px 0; font-size: 13px; }
.drill-totals { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.drill-totals span, .dimension-chip { background: #eef2ff; border-radius: 999px; padding: 4px 10px; font-size: 12px; white-space: nowrap; }
.dimension-bar { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
.hit-table { margin: 10px 0; }
.reason-check { display: flex; gap: 8px; align-items: flex-start; padding: 6px 0; cursor: pointer; }
.reason-check small { display: block; color: var(--muted); margin-top: 3px; }
.chip { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; background: #e2e8f0; margin-right: 4px; }
.chip.danger { background: #fee2e2; color: #b42318; }
.chip.success { background: #dcfce7; color: #166534; }
.json-box { background: #0f172a; color: #e2e8f0; padding: 8px; border-radius: 6px; max-height: 180px; overflow: auto; font-size: 12px; text-align: left; }
.muted { color: var(--muted); font-size: 12px; }
.drill-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 10px; }
.success-banner { display: flex; justify-content: space-between; align-items: center; gap: 12px; background: #ecfdf5; border: 1px solid #6ee7b7; border-radius: 8px; padding: 10px; margin: 10px 0; font-size: 13px; }
.confirm-list { max-height: 220px; overflow: auto; padding-left: 20px; font-size: 13px; }
.wide-modal { width: min(900px, 100%); }
.reason-list { padding-left: 18px; font-size: 13px; display: grid; gap: 8px; }
.round-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px; margin: 8px 0; font-size: 13px; }
.round-card header { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.round-card ul { margin: 6px 0; padding-left: 18px; }
button:disabled { opacity: .55; cursor: not-allowed; }
</style>

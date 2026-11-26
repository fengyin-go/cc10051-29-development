<template>
  <section class="page quality-recheck-page" data-module="quality_recheck">
    <header class="page-head">
      <div>
        <h2>质量复查展示 · 重检清单</h2>
        <p class="page-desc">
          按实体和报告轮次筛出真正受影响的记录；同一行可展示多项命中理由，但重检工作和所属记录只预约一次。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" data-testid="simulate-late-input-global" type="button" @click="deliverLateInput()">
          模拟迟到清洗输入
        </button>
        <button class="btn primary" data-testid="refresh-list" type="button" @click="loadList">
          刷新重检视图
        </button>
      </div>
    </header>

    <div class="notice-grid">
      <div class="info-banner">
        <strong>去重口径</strong>
        <span>清单按「原报告身份 + 实体 + 记录」去重；理由可以有两项，X 不会被当成两笔重检。</span>
      </div>
      <div v-if="lateMessage" class="info-banner warning" data-testid="late-input-message">
        <strong>输入动态</strong>
        <span>{{ lateMessage }}</span>
      </div>
      <div v-if="notice" class="info-banner success" data-testid="action-message">{{ notice }}</div>
      <p v-if="errorMessage" class="error-text" data-testid="error-message">{{ errorMessage }}</p>
    </div>

    <form class="filter-bar recheck-filters" @submit.prevent="loadList">
      <label class="filter-item">
        <span>实体 / 实体编码</span>
        <input v-model="filters.entity_code" data-testid="filter-entity" placeholder="例如 CUSTOMER" />
      </label>
      <label class="filter-item">
        <span>报告轮次</span>
        <input v-model="filters.report_round" data-testid="filter-report-round" placeholder="例如 R1" />
      </label>
      <label class="filter-item">
        <span>重检批次</span>
        <input v-model="filters.batch_code" data-testid="filter-batch" placeholder="RCB..." />
      </label>
      <label class="filter-item">
        <span>状态</span>
        <select v-model="filters.status" data-testid="filter-status">
          <option value="">全部状态</option>
          <option>待领取</option>
          <option>处理中</option>
          <option>已完成</option>
        </select>
      </label>
      <label class="filter-item">
        <span>记录 / 单号关键字</span>
        <input v-model="filters.keyword" data-testid="filter-keyword" placeholder="X / RC-X" />
      </label>
      <button class="btn primary" data-testid="recheck-query" type="submit">查询受影响记录</button>
      <button class="btn ghost" type="button" data-testid="recheck-reset" @click="resetFilters">重置</button>
    </form>

    <div class="stat-row" data-testid="recheck-stats">
      <article class="stat-card">
        <span class="stat-label">重检清单 / 所属记录</span>
        <strong class="stat-value">{{ totals.item_count ?? items.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">去重后记录数</span>
        <strong class="stat-value">{{ totals.record_count ?? items.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">命中理由总数</span>
        <strong class="stat-value">{{ totals.reason_count ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">处理中</span>
        <strong class="stat-value">{{ statusCount('处理中') }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已完成</span>
        <strong class="stat-value">{{ statusCount('已完成') }}</strong>
      </article>
    </div>

    <table class="data-table" data-testid="recheck-table">
      <thead>
        <tr>
          <th>重检单号 / 批次</th>
          <th>原报告 / 轮次</th>
          <th>实体</th>
          <th>真正受影响记录</th>
          <th>理由</th>
          <th>检查总数核对</th>
          <th>状态 / 复查员</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in items"
          :key="item.id"
          :data-testid="`recheck-row-${item.id}`"
          :data-record="item.record_id"
          :data-status="item.status"
        >
          <td>
            <strong>{{ item.recheck_code }}</strong>
            <div>{{ item.batch_code }}</div>
          </td>
          <td>
            <div>{{ item.report_batch }}</div>
            <span class="chip">轮次 {{ item.report_round }}</span>
          </td>
          <td>{{ item.entity_code }}</td>
          <td><strong data-testid="record-x">{{ item.record_label || item.record_id }}</strong>（{{ item.record_id }}）</td>
          <td>
            <span class="chip danger">原理由 {{ item.original_reason_count }}</span>
            <span class="chip" :class="item.current_run?.hit_count ? 'danger' : 'success'">
              当前 {{ item.current_run?.hit_count ?? item.current_reason_count }}
            </span>
          </td>
          <td>
            规则检查 {{ item.current_run?.check_total ?? item.reason_count }} 项；
            重检 <strong>1</strong> 笔
          </td>
          <td>
            <span :data-testid="`recheck-status-${item.id}`">{{ item.status }}</span>
            <div class="muted">{{ item.assignee || '未领取' }}</div>
          </td>
          <td class="row-actions">
            <button class="link" type="button" :data-testid="`claim-recheck-${item.id}`" @click="claim(item)">
              {{ item.claimed ? '继续领取/办理' : '领取该条重检' }}
            </button>
            <button class="link" type="button" :data-testid="`refresh-recheck-${item.id}`" @click="refresh(item)">
              刷新
            </button>
            <button class="link" type="button" :data-testid="`confirm-recheck-${item.id}`" @click="confirm(item)">
              服务端确认结果
            </button>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="8" class="empty-state">当前实体 / 报告轮次下没有真正受影响的重检记录</td>
        </tr>
      </tbody>
    </table>

    <section
      v-for="item in items"
      :key="`detail-${item.id}`"
      class="recheck-card"
      :data-testid="`recheck-card-${item.id}`"
      :data-record="item.record_id"
    >
      <header class="card-head">
        <div>
          <h3>记录 {{ item.record_label || item.record_id }} 的重检清单</h3>
          <p>{{ item.recheck_code }} · {{ item.batch_code }} · 原报告 {{ item.report_batch }} · 轮次 {{ item.report_round }}</p>
          <p class="muted" data-testid="missing-fields-summary">
            原检查时该记录缺少两项字段：{{ item.original_reasons?.map((reason: any) => reason.field).join('、') }}；
            两项维度分别保留理由，但只生成一笔重检。
          </p>
        </div>
        <div class="page-actions">
          <button class="btn" type="button" :data-testid="`card-claim-${item.id}`" @click="claim(item)">领取</button>
          <button class="btn" type="button" :data-testid="`card-refresh-${item.id}`" @click="refresh(item)">刷新并重算输入</button>
          <button class="btn primary" type="button" :data-testid="`card-confirm-${item.id}`" @click="confirm(item)">
            确认重检结果
          </button>
        </div>
      </header>

      <p class="reconcile" :data-testid="`count-reconcile-${item.id}`">
        重检批次清单检查总数：<strong>1</strong> 笔所属记录（X 不会被当成两笔）；
        可核对的规则检查项：<strong>{{ item.batch?.rule_check_total ?? item.current_run?.check_total ?? item.reason_count }}</strong> 项；
        原报告理由：<strong>{{ item.original_reason_count }}</strong> 项；
        当前输入重跑剩余：<strong>{{ item.current_run?.hit_count ?? item.current_reason_count }}</strong> 项。
        同一行两项维度只预约一次，预约次数={{ item.reservation_count }}。
      </p>

      <div v-if="item.input_conflict" class="conflict-box" :data-testid="`conflict-${item.id}`">
        <strong>检测到输入与原凭据冲突</strong>
        <p>{{ item.conflict_message }}</p>
        <div v-if="item.comparison" class="comparison">
          <div>原输入试算剩余：{{ item.comparison.original_run.hit_count }} 项</div>
          <div>最新输入试算剩余：{{ item.comparison.latest_run.hit_count }} 项</div>
        </div>
        <button class="btn" type="button" :data-testid="`simulate-late-item-${item.id}`" @click="deliverLateInput(item)">
          再次送达迟到输入
        </button>
      </div>

      <div class="recheck-grid">
        <div class="panel">
          <h4>原报告命中原因（继续可回查）</h4>
          <ul class="reason-list" :data-testid="`original-reasons-${item.id}`">
            <li v-for="reason in item.original_reasons" :key="reason.id" :data-testid="`reason-${reason.id}`">
              <div class="reason-title">
                <span class="chip danger">{{ reason.dimension }}</span>
                <strong>{{ reason.rule_name }}</strong>
              </div>
              <p>{{ reason.reason }}</p>
              <p class="muted">检查依据：{{ reason.rule_standard }}</p>
              <details>
                <summary>查看原行内容 / 原凭据</summary>
                <pre>{{ JSON.stringify(reason.original_row, null, 2) }}</pre>
              </details>
            </li>
          </ul>

          <h4>采用当前输入后的剩余理由</h4>
          <div :data-testid="`current-reasons-${item.id}`">
            <p v-if="!item.current_run?.checks?.length" class="muted">尚未重跑。</p>
            <p v-else-if="item.current_run.hit_count === 0" class="chip success" data-testid="current-no-hit">
              无剩余命中理由，两项检查均通过
            </p>
            <ul v-else class="reason-list">
              <li
                v-for="check in item.current_run.checks.filter((entry: any) => entry.hit)"
                :key="check.rule_id"
                data-current-reason="true"
              >
                <div class="reason-title">
                  <span class="chip danger">{{ check.result }}</span>
                  <strong>{{ check.dimension }}</strong>
                </div>
                <p>{{ check.reason }}</p>
                <p class="muted">采用标准：{{ check.rule_standard }}；输入：{{ check.input_id }}（{{ check.source_credential }}）</p>
              </li>
            </ul>
            <div v-if="item.current_run?.passed_count" class="passed-checks" data-testid="passed-checks">
              <span class="chip success">已通过 {{ item.current_run.passed_count }} 项</span>
              <span
                v-for="check in item.current_run.checks.filter((entry: any) => entry.passed)"
                :key="`passed-${check.rule_id}`"
                class="muted"
              >
                {{ check.dimension }}（实际值：{{ check.actual_value }}）
              </span>
            </div>
          </div>
        </div>

        <div class="panel">
          <h4>受影响检查数据与处置范围</h4>
          <p :data-testid="`scope-${item.id}`">{{ item.disposition_scope }}</p>
          <p><strong>规则实际取得的输入：</strong>{{ item.effective_input?.input_code || '—' }}</p>
          <p class="muted">
            输入类型：{{ item.effective_input?.kind }}；凭据：{{ item.effective_input?.source_credential }}；
            到达时间：{{ item.effective_input?.received_at }}
          </p>

          <label class="input-choice">
            <span>确认时采用的检查输入</span>
            <select v-model="inputChoices[item.id]" :data-testid="`input-choice-${item.id}`">
              <option
                v-for="input in item.available_inputs"
                :key="input.input_code"
                :value="input.input_code"
              >
                {{ input.input_code }} · {{ input.label }} · {{ input.source_credential }}
              </option>
            </select>
          </label>
          <div class="page-actions">
            <button class="btn" type="button" :data-testid="`rerun-with-input-${item.id}`" @click="rerun(item)">
              按所选检查依据试跑
            </button>
            <button
              class="btn"
              type="button"
              :data-testid="`open-actual-input-${item.id}`"
              @click="toggleInput(item.id)"
            >
              打开实际使用的输入
            </button>
          </div>
          <pre
            v-if="openInputId === item.id"
            class="json-box"
            data-testid="actual-input-content"
          >{{ JSON.stringify(item.effective_input, null, 2) }}</pre>

          <details class="all-inputs">
            <summary>查看全部输入版本（含原报告凭据）</summary>
            <div v-for="input in item.available_inputs" :key="input.input_code" class="input-version">
              <strong>{{ input.input_code }} · {{ input.label }}</strong>
              <p class="muted">{{ input.source_credential }} · {{ input.received_at }}</p>
              <pre>{{ JSON.stringify(input.rows?.find((row: any) => String(row.record_id) === String(item.record_id)) || input, null, 2) }}</pre>
            </div>
          </details>

          <div v-if="item.rerun_result" class="result-box" :data-testid="`final-result-${item.id}`">
            <h4>本次确认结果</h4>
            <p>处置结论：{{ item.处置结论 }}</p>
            <p>重跑 {{ item.rerun_result.check_total }} 项，通过 {{ item.rerun_result.passed_count }} 项，剩余命中 {{ item.rerun_result.hit_count }} 项，得分 {{ item.rerun_result.score }}</p>
            <p>采用检查依据：{{ item.result_report_id ? '已写入新报告轮次' : '' }}</p>
            <RouterLink
              v-if="item.result_report_id"
              class="btn primary"
              :data-testid="`view-report-${item.id}`"
              :to="`/quality_result?report=${item.result_report_id}`"
            >
              回看原命中和本次报告结果
            </RouterLink>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import { qualityGet, qualityPost, queryString, type QualityJson } from '@/api/quality'

const route = useRoute()
const items = ref<QualityJson[]>([])
const batches = ref<QualityJson[]>([])
const totals = ref<QualityJson>({})
const loading = ref(false)
const errorMessage = ref('')
const notice = ref('')
const lateMessage = ref('')
const openInputId = ref<number | string | null>(null)
const inputChoices = reactive<Record<string, string>>({})

const filters = reactive({
  entity_code: '',
  report_round: '',
  batch_code: '',
  status: '',
  keyword: '',
})

function statusCount(status: string): number {
  return items.value.filter((item) => item.status === status).length
}

function replaceItem(updated: QualityJson) {
  const index = items.value.findIndex((item) => String(item.id) === String(updated.id))
  if (index >= 0) items.value[index] = updated
  else items.value.unshift(updated)
  const code = updated.effective_input?.input_code
  if (code) inputChoices[String(updated.id)] = code
}

async function loadList() {
  loading.value = true
  errorMessage.value = ''
  try {
    if (route.query.entity && !filters.entity_code) filters.entity_code = String(route.query.entity)
    if (route.query.round && !filters.report_round) filters.report_round = String(route.query.round)
    if (route.query.batch && !filters.batch_code) filters.batch_code = String(route.query.batch)
    const query = queryString({ ...filters })
    const data = await qualityGet(`/api/quality-workflow/rechecks${query}`)
    items.value = data.items || []
    batches.value = data.batches || []
    totals.value = data.totals || {}
    items.value.forEach((item) => {
      const code = item.effective_input?.input_code
      if (code && !inputChoices[String(item.id)]) inputChoices[String(item.id)] = code
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '质量复查清单读取失败'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.entity_code = ''
  filters.report_round = ''
  filters.batch_code = ''
  filters.status = ''
  filters.keyword = ''
  void loadList()
}

async function claim(item: QualityJson) {
  errorMessage.value = ''
  notice.value = ''
  try {
    const data = await qualityPost(`/api/quality_recheck/${item.id}/claim`, { reviewer: '复查员' })
    replaceItem(data.item)
    notice.value = data.message || '已领取'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '领取失败'
  }
}

async function refresh(item: QualityJson) {
  errorMessage.value = ''
  notice.value = ''
  try {
    const data = await qualityPost(`/api/quality_recheck/${item.id}/refresh`, { adopt: 'latest' })
    replaceItem(data.item)
    const current = data.item?.current_run?.hit_count
    notice.value = `已刷新：原报告两项理由保留可查，采用最新输入后当前剩余 ${current} 项理由。`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新失败'
  }
}

async function deliverLateInput(item?: QualityJson) {
  errorMessage.value = ''
  try {
    const path = item
      ? `/api/quality_recheck/${item.id}/simulate-late-input`
      : '/api/quality-workflow/late-inputs'
    const data = await qualityPost(path, {})
    lateMessage.value = data.message || '迟到清洗输入已送达，请刷新重检视图。'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '迟到输入登记失败'
  }
}

async function rerun(item: QualityJson) {
  errorMessage.value = ''
  notice.value = ''
  try {
    const inputId = inputChoices[String(item.id)] || item.effective_input?.input_code
    const data = await qualityPost(`/api/quality_recheck/${item.id}/rerun`, { input_id: inputId })
    replaceItem(data.item)
    notice.value = `规则已取得 ${data.result?.input_id} 试跑：当前剩余 ${data.result?.hit_count} 项理由。`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '规则试跑失败'
  }
}

async function confirm(item: QualityJson) {
  errorMessage.value = ''
  notice.value = ''
  try {
    const inputId = inputChoices[String(item.id)] || item.effective_input?.input_code
    const data = await qualityPost(`/api/quality_recheck/${item.id}/confirm`, {
      input_id: inputId,
      reviewer: '复查员',
      remark: '服务端按所选实际输入和规则标准确认',
    })
    replaceItem(data.item)
    notice.value = data.message || '重检结果已确认并写回质量报告'
    await loadList()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '服务端确认重检失败'
  }
}

function toggleInput(id: number | string) {
  openInputId.value = openInputId.value === id ? null : id
}

onMounted(loadList)
</script>

<style scoped>
.quality-recheck-page { display: flex; flex-direction: column; gap: 12px; }
.notice-grid { display: grid; gap: 8px; }
.info-banner { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px 12px; font-size: 13px; display: flex; gap: 10px; }
.info-banner.warning { background: #fffbeb; border-color: #fcd34d; }
.info-banner.success { background: #ecfdf5; border-color: #6ee7b7; }
.recheck-filters { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.recheck-filters select { padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; min-width: 150px; }
.recheck-card { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
.card-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.card-head h3 { margin: 0 0 4px; }
.card-head p { margin: 0; color: var(--muted); font-size: 12px; }
.reconcile { background: #f8fafc; border-left: 3px solid var(--brand); padding: 10px; font-size: 13px; }
.chip { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; background: #e2e8f0; margin: 1px 2px; }
.chip.danger { background: #fee2e2; color: #b42318; }
.chip.success { background: #dcfce7; color: #166534; }
.conflict-box { border: 1px solid #f59e0b; background: #fffbeb; border-radius: 8px; padding: 10px 12px; }
.comparison { display: flex; gap: 16px; font-size: 13px; margin: 6px 0; }
.recheck-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr); gap: 14px; margin-top: 12px; }
.panel { border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
.panel h4 { margin: 0 0 8px; }
.reason-list { list-style: none; margin: 0 0 14px; padding: 0; display: grid; gap: 8px; }
.reason-list li { border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
.reason-list li.passed { background: #f0fdf4; }
.passed-checks { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 6px 0 12px; }
.reason-title { display: flex; align-items: center; gap: 8px; }
.reason-list p { margin: 6px 0; font-size: 13px; }
.muted { color: var(--muted); font-size: 12px; }
.json-box { background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 8px; overflow: auto; max-height: 320px; font-size: 12px; }
.input-choice { display: grid; gap: 4px; font-size: 12px; margin: 10px 0; }
.input-choice select { padding: 7px; border: 1px solid var(--border); border-radius: 6px; }
.all-inputs, .input-version { margin-top: 10px; }
.result-box { margin-top: 12px; border-top: 1px solid var(--border); padding-top: 10px; }
@media (max-width: 1100px) { .recheck-grid { grid-template-columns: 1fr; } }
</style>

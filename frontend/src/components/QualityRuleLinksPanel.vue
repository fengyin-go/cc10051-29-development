<template>
  <section class="rule-link-panel" data-testid="quality-rule-links">
    <div class="panel-head">
      <h3>重检请求 · 原报告输入 · 实际采用输入</h3>
      <button class="btn" type="button" data-testid="reload-rule-links" @click="load">刷新关联</button>
    </div>
    <p class="muted">
      质量规则库按重检请求关联重检清单和原报告实际输入；确认后可在此打开规则实际使用的输入与新一轮报告结果。
    </p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <article v-for="context in contexts" :key="context.rule.id" class="rule-card" :data-testid="`rule-context-${context.rule.id}`">
      <header>
        <div>
          <strong>{{ context.rule.规则名称 }}</strong>
          <span class="chip">{{ context.rule.检查维度 }}</span>
        </div>
        <span class="muted">{{ context.rule.rule_standard }}</span>
      </header>

      <div class="link-grid">
        <div>
          <h4>关联重检清单</h4>
          <p v-if="!context.recheck_requests?.length" class="muted">暂无重检请求</p>
          <div v-for="link in context.recheck_requests" :key="link.recheck_item_id" class="link-item">
            <RouterLink :to="`/quality_recheck?batch=${link.batch_code}`" data-testid="rule-recheck-link">
              {{ link.recheck_code }} / {{ link.batch_code }} / 记录 {{ link.record_id }}
            </RouterLink>
            <span>原报告：{{ link.report_batch }}</span>
            <ul>
              <li v-for="check in link.checklist" :key="check.id">{{ check.dimension }}：{{ check.reason }}</li>
            </ul>
          </div>
        </div>

        <div>
          <h4>实际输入</h4>
          <button
            v-if="context.actual_inputs?.length"
            class="btn primary input-open-btn"
            type="button"
            :data-testid="`open-rule-latest-input-${context.rule.id}`"
            @click="toggle(`${context.rule.id}-${context.actual_inputs[context.actual_inputs.length - 1].id}`)"
          >
            打开实际使用的输入
          </button>
          <p v-for="input in context.actual_inputs" :key="input.input_code">
            <button
              class="link"
              type="button"
              :data-testid="`open-rule-input-${context.rule.id}-${input.id}`"
              @click="toggle(`${context.rule.id}-${input.id}`)"
            >
              {{ input.input_code }} · {{ input.label }} · {{ input.source_credential }}
            </button>
            <pre
              v-if="openKey === `${context.rule.id}-${input.id}`"
              class="json-box"
              data-testid="rule-actual-input-content"
            >{{ JSON.stringify(input, null, 2) }}</pre>
          </p>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { qualityGet, type QualityJson } from '@/api/quality'

const contexts = ref<QualityJson[]>([])
const errorMessage = ref('')
const openKey = ref('')

async function load() {
  try {
    const data = await qualityGet('/api/quality-workflow/rule-links')
    contexts.value = data.items || []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '规则关联读取失败'
  }
}

function toggle(key: string) {
  openKey.value = openKey.value === key ? '' : key
}

onMounted(load)
</script>

<style scoped>
.rule-link-panel { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 14px; margin-bottom: 12px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
.panel-head h3 { margin: 0; }
.muted { color: var(--muted); font-size: 12px; }
.rule-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px; margin-top: 10px; }
.rule-card header { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.chip { background: #e0e7ff; border-radius: 999px; padding: 2px 8px; font-size: 12px; margin-left: 8px; }
.link-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 8px; }
.link-item { border-left: 3px solid var(--brand); padding-left: 8px; margin: 8px 0; font-size: 13px; }
.link-item ul { margin: 4px 0; padding-left: 18px; }
.json-box { background: #0f172a; color: #e2e8f0; padding: 10px; border-radius: 8px; max-height: 280px; overflow: auto; font-size: 12px; }
.input-open-btn { margin-bottom: 8px; }
@media (max-width: 1000px) { .link-grid { grid-template-columns: 1fr; } }
</style>

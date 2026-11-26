<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ moduleName(row.name) }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'
import { MODULE_BY_KEY } from '@/data/modules'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])

function moduleName(key: string): string {
  return MODULE_BY_KEY.get(key)?.name ?? key
}

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}]
    moduleRows.value = [{"name": "源系统登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "主数据实体", "created": 0, "pending": 0, "abnormal": 0}, {"name": "记录抽取作业", "created": 0, "pending": 0, "abnormal": 0}, {"name": "标准化清洗", "created": 0, "pending": 0, "abnormal": 0}, {"name": "重复检测器", "created": 0, "pending": 0, "abnormal": 0}, {"name": "金记录合并", "created": 0, "pending": 0, "abnormal": 0}, {"name": "金记录发布", "created": 0, "pending": 0, "abnormal": 0}, {"name": "下游订阅方", "created": 0, "pending": 0, "abnormal": 0}, {"name": "分发任务", "created": 0, "pending": 0, "abnormal": 0}, {"name": "血缘关系图", "created": 0, "pending": 0, "abnormal": 0}, {"name": "质量规则库", "created": 0, "pending": 0, "abnormal": 0}, {"name": "质量报告", "created": 0, "pending": 0, "abnormal": 0}, {"name": "合并复核队列", "created": 0, "pending": 0, "abnormal": 0}, {"name": "版本回滚器", "created": 0, "pending": 0, "abnormal": 0}, {"name": "同步游标", "created": 0, "pending": 0, "abnormal": 0}, {"name": "标识交叉映射", "created": 0, "pending": 0, "abnormal": 0}, {"name": "分发回执中心", "created": 0, "pending": 0, "abnormal": 0}, {"name": "实体变更审批", "created": 0, "pending": 0, "abnormal": 0}, {"name": "治理看板数据", "created": 0, "pending": 0, "abnormal": 0}, {"name": "参考数据管理", "created": 0, "pending": 0, "abnormal": 0}]
  }
})
</script>

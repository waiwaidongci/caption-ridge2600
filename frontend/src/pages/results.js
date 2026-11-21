import {plot} from '../components/common/chart.js';
import {feedback} from '../components/common/fields.js';
import {empty, metrics, panel, pill} from '../components/common/panels.js';
import {table} from '../components/common/table.js';
import {REVIEW, STATUS} from '../constants/enums.js';
import {handler, poll} from '../hooks/action.js';
import {workspace} from '../stores/workspace.js';
import {button, el, h, link, p} from '../utils/dom.js';
import {date, value} from '../utils/format.js';

function tracer() {
  const message = feedback();
  const output = el('div');
  const submit = button('查询溯源', {type:'submit', class:'quiet', 'data-testid':'trace-submit'});
  const form = el('form', {class:'fields', onSubmit:handler(submit, message, async event => {
    const id = new FormData(event.target).get('job_id')?.trim();
    if (!id) throw new Error('请填写工单号');
    const data = await workspace.order(id);
    output.replaceChildren(
      table([{label:'收到时间', render:row=>date(row.received_at)}, {key:'dataset', label:'批次'},
        {key:'actual_minutes', label:'实耗分钟'}], data.records, {caption:'工单版本时间线'}),
      data.estimates.length ? table([
        {key:'schedule_day', label:'排班日'}, {key:'estimated_minutes', label:'估算分钟'},
        {key:'flagged', label:'标记'}, {key:'estimate_source', label:'估算依据'},
        {key:'verify_actual', label:'验算实耗'}, {key:'verify_error', label:'估算减实耗'},
        {key:'verify_source', label:'验算依据'},
      ], data.estimates, {caption:'排班日估算与验算溯源'}) : p('该单还没有排班日估算。', 'subtle'));
  })}, el('label', {class:'field', for:'trace-job'}, el('span', {}, '工单号'),
    el('input', {id:'trace-job', name:'job_id', type:'text', required:true, maxlength:64, placeholder:'如 QJ-N01'})),
    submit, message);
  return panel('工单溯源', p('查看每个排班日估算与验算各用了哪份工单记录。', 'subtle'), form, output);
}

export async function results(route, refresh) {
  const {spec,runs,datasets} = workspace;
  const id = route.id || runs[0]?.id;
  if (!id) return panel(spec.pages[3],empty('还没有可查看的运行结果。','#run','前往运行'));
  const job = await workspace.getRun(id);
  const source = datasets.find(item => item.id === job.dataset_id);
  const message = feedback();
  const finished = item => item.status === 'complete' || item.status === 'failed';
  if (!finished(job)) {
    const original = location.hash;
    const status = el('p',{role:'status'},'后台正在计算，完成后会自动展示。');
    poll(()=>workspace.getRun(id),finished,()=>location.hash===original)
      .then(result=>{if (result && status.isConnected && location.hash===original) refresh();
        else if(status.isConnected) status.textContent='仍在执行，请点击刷新检查。';})
      .catch(error=>{if(status.isConnected) status.textContent=error.message;});
    return panel(job.name,pill(STATUS[job.status],job.status),status,button('刷新',{class:'quiet',onClick:refresh}));
  }
  const download = button('下载结果 CSV',{class:'quiet','data-testid':'export',onClick:event=>
    handler(download,message,()=>workspace.download(`/runs/${job.id}/export`,`${spec.short_name}-${job.id}.csv`))(event)});
  const history = el('label',{class:'field run-picker',for:'run-picker'},el('span',{},'切换运行记录'),
    el('select',{id:'run-picker',onChange:event=>{location.hash=`#results/${event.target.value}`;}},
      (runs.some(item=>item.id===job.id) ? runs : [job,...runs]).map(item=>el('option',{value:item.id,selected:item.id===job.id},item.name))));
  const result = job.result;
  const analysis = result ? el('section',{class:'analysis','data-testid':'analysis-complete'},
    el('div',{class:'result-head'},p(job.name,'eyeline'),h(2,result.headline),p(result.note,'intro-copy'),
      el('div',{class:'actions'},pill(STATUS[job.status],job.status),download,message)),
    metrics(result.metrics),
    result.charts.map(plot),
    (result.sections || []).map(item=>panel(item.title,p(item.text))),
    result.tables.map(item=>panel(item.title,table(item.columns,item.rows,{caption:item.title}))))
    : panel(job.name,pill(STATUS[job.status],job.status),p(job.error,'feedback'),link('返回调整参数',`#run/${job.dataset_id}`,{class:'quiet'}));
  const inputs = spec.params.map(param=>el('div',{},el('dt',{},param.label),el('dd',{},value(job.params[param.key]))));
  return el('div',{},el('div',{class:'two-col'},el('div',{class:'wide-panel'},analysis),
    el('aside',{class:'sidebar-panel'},panel('运行来源',history,
      source && link(source.name,`#inputs/${source.id}`),p(date(job.finished_at),'subtle'),
      job.snapshot_id != null && p(`版本快照 #${job.snapshot_id}`,'subtle'),
      el('dl',{class:'dictionary'},inputs)),
    result && panel(spec.decision, pill(REVIEW[job.review],job.review),
      link('打开复核记录',`#review/${job.id}`,{class:'quiet'})),
    tracer())));
}

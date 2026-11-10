import json, os, shutil, numpy as np
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
cov=set(json.load(open(REPO/'verification/operator-audit-7.0.10/l3_route_coverage.json'))['covered_ids'])
bp=json.load(open(REPO/'library/seed/operon/builtin_packages.json'))
ds={x['id']:x for p in bp['packages'] for x in p.get('descriptors',[])}
ids=[]
for i,x in ds.items():
    if i in cov or x.get('kind')!='operator' or x.get('category')!='Statistics': continue
    ins=x.get('contracts',{}).get('inputs',[])
    if len(ins)!=1 or len(ins[0].get('dims',[]))!=2: continue
    props=(x.get('parameters_schema') or {}).get('properties',{})
    if any(k in props for k in ['response_label','outcome_label','time_label','event_label','predictors','covariates']):
        ids.append(i)
print('ids',len(ids))
rng=np.random.default_rng(7); n=80
x=rng.normal(size=(n,8))
y=1+2*x[:,0]-0.5*x[:,1]+rng.normal(scale=.3,size=n)
ybin=(1/(1+np.exp(-(-0.5+1.2*x[:,0]-0.4*x[:,1])))>rng.random(n)).astype(int)
cnt=rng.poisson(np.exp(0.3+0.4*x[:,0]))
t=np.abs(1.5+0.8*x[:,0]+rng.normal(scale=.3,size=n))+0.1
e=(rng.random(n)<0.7).astype(int)
g=np.array(['A','B','C'])[np.arange(n)%3]
s=np.arange(n)%2
risk=1/(1+np.exp(-(x[:,0]+x[:,1])))
old=1/(1+np.exp(-(0.8*x[:,0]))); new=1/(1+np.exp(-(1.1*x[:,0]+0.2*x[:,1])))
treat=(np.arange(n)%2)
tl=t-0.1; tu=t+0.2
cols=['y','ybin','cnt','t','e','g','s','risk','old','new','treat','tl','tu']+[f'x{k}' for k in range(1,9)]
arr=np.column_stack([y,ybin,cnt,t,e,g,s,risk,old,new,treat,tl,tu,x])
out=Path('/tmp/regstats'); shutil.rmtree(out,ignore_errors=True); out.mkdir(parents=True)
for i in ids:
    x_des=ds[i]; props=(x_des.get('parameters_schema') or {}).get('properties',{})
    d=out/i; (d/'input').mkdir(parents=True)
    with open(d/'input'/'data.csv','w') as f:
        f.write('sample,'+','.join(cols)+'\n')
        for r in range(n): f.write(f's{r},'+','.join(str(v) for v in arr[r])+'\n')
    params={}
    for k,v in props.items():
        if 'default' in v: params[k]=v['default']
        elif v.get('type')=='boolean': params[k]=False
        elif v.get('type')=='integer': params[k]=1
        elif v.get('type')=='number': params[k]=0.05
        elif v.get('type')=='array': params[k]=[]
        elif v.get('type')=='string': params[k]=''
    ov={'response_label':'y','outcome_label':'ybin','time_label':'t','event_label':'e','predictors':['x1','x2','x3'],'covariates':['x1','x2','x3'],'fixed_effects':['x1','x2'],'group_label':'g','stratum_label':'s','treatment_label':'treat','endog_labels':['x1'],'instrument_labels':['x2'],'risk_label':'risk','old_risk_label':'old','new_risk_label':'new','probability_label':'risk','predictor_label':'x1','running_label':'x1','count_predictors':['x1','x2'],'zero_predictors':['x3'],'time_lower_label':'tl','time_upper_label':'tu','output':i}
    for k,v in ov.items():
        if k in props: params[k]=v
    # choose response column for count models
    if i in ('poisson_regression','negative_binomial_regression','zero_inflated_poisson','zero_inflated_negative_binomial'):
        if 'response_label' in props: params['response_label']='cnt'
    (d/'parameters.json').write_text(json.dumps({'format':'biopipe.task-parameters','schema_version':1,'params':{},'sources':{'data':{}},'steps':[{'name':i,'inputs':['data'],'params':params,'context_params':{}},{'name':'export_results','inputs':[i],'params':{'filename':i},'context_params':{}}]},indent=2))
    (d/'task.yaml').write_text(json.dumps({'format':'operon.task','version':1,'name':i,'sources':{'data':{'reader':'CsvReader','path':'input/data.csv','dims':['sample','feature'],'labels':{'sample':{'feature':0},'feature':'builtin'}}},'steps':[{'name':i,'inputs':['data']},{'name':'export_results','inputs':[i]}]},indent=2))
print('generated',len(ids))

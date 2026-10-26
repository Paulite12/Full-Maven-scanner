"""Train an optional baseline model from a user-supplied labelled CSV.

Expected columns: observed_at, relative_volume, change_5m, change_24h,
turnover_24h, future_return_pct. The future return must be measured AFTER
observed_at. This script deliberately refuses tiny datasets and uses a
chronological split to reduce leakage. It does not make a model profitable.
"""
import argparse, json
from pathlib import Path
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

FEATURES=['relative_volume','change_5m','change_24h','turnover_24h']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('csv',help='CSV with post-observation forward returns');ap.add_argument('--target-pct',type=float,default=10.0,help='Target event: future_return_pct >= this threshold');ap.add_argument('--out',default='artifacts/baseline_model.joblib');args=ap.parse_args()
    df=pd.read_csv(args.csv)
    required=FEATURES+['future_return_pct','observed_at']
    missing=[c for c in required if c not in df.columns]
    if missing:raise SystemExit('Missing required columns: '+', '.join(missing))
    df['observed_at']=pd.to_datetime(df['observed_at'],utc=True,errors='coerce')
    for col in FEATURES+['future_return_pct']:
        df[col]=pd.to_numeric(df[col],errors='coerce')
    df=df.dropna(subset=['observed_at','future_return_pct']).sort_values('observed_at')
    if len(df)<500:raise SystemExit(f'Need at least 500 labelled observations; found {len(df)}. More data is needed for a meaningful baseline.')
    df['target']=(pd.to_numeric(df['future_return_pct'],errors='coerce')>=args.target_pct).astype(int);df=df.dropna(subset=FEATURES)
    cut=int(len(df)*.8);train,test=df.iloc[:cut],df.iloc[cut:]
    if train.target.nunique()<2 or test.target.nunique()<2:raise SystemExit('Both chronological train and test portions must contain positive and negative examples.')
    model=Pipeline([('imputer',SimpleImputer(strategy='median')),('scale',StandardScaler()),('model',RandomForestClassifier(n_estimators=300,min_samples_leaf=5,class_weight='balanced',random_state=42,n_jobs=-1))])
    model.fit(train[FEATURES],train.target);pred=model.predict(test[FEATURES]);proba=model.predict_proba(test[FEATURES])[:,1]
    report=classification_report(test.target,pred,output_dict=True,zero_division=0)
    metrics={'rows':len(df),'train_rows':len(train),'test_rows':len(test),'target_definition':f'future_return_pct >= {args.target_pct}','positive_rate_test':float(test.target.mean()),'roc_auc':float(roc_auc_score(test.target,proba)),'classification_report':report,'warning':'Research baseline only. Validate costs, leakage, survivorship bias and calibration before considering use.'}
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);joblib.dump({'model':model,'features':FEATURES,'target_pct':args.target_pct},out);out.with_suffix('.metrics.json').write_text(json.dumps(metrics,indent=2));print(json.dumps(metrics,indent=2));print(f'Model saved to {out}')
if __name__=='__main__':main()

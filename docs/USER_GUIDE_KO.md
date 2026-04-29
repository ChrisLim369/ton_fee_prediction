# TON 거래 수수료 예측 프로젝트 사용설명서

프로젝트 위치:

```bash
/Users/changhyuklim/ton_fee_prediction
```

이 프로젝트는 TON Center API v3에서 TON 온체인 거래 데이터를 수집하고, 시간별 feature를 만든 뒤, 다음 1시간 평균 거래 수수료를 예측합니다. 현재는 선형 모델뿐 아니라 직접 구현한 비선형 gradient-boosted tree 모델까지 비교합니다.

## 전체 흐름

```text
TON Center API v3 거래 데이터 수집
-> raw_transactions.csv 저장
-> hash + lt 기준 중복 제거
-> hourly_features.csv 생성
-> 여러 모델 학습 및 비교
-> rolling backtest로 안정성 평가
-> best_model.json 저장
-> 다음 24시간 예측 predictions.csv 생성
-> SVG 그래프 생성
```

## 현재 데이터 상태

최신 검증 기준:

```text
raw 거래 수: 3,612,967
중복 거래 수(hash + lt): 0
시간별 feature row 수: 726
예측 row 수: 24
raw 데이터 범위: 2026-03-29T06:00:07Z ~ 2026-04-28T11:06:10Z
예측 범위: 2026-04-28T12:00:00Z ~ 2026-04-29T11:00:00Z
```

주의:

```text
수집 window가 여전히 page limit에 도달합니다.
따라서 tx_count와 unique_accounts는 전체 체인 수치가 아니라 sample count로 봐야 합니다.
```

## 현재 모델 상태

단일 chronological holdout 기준 best model:

```text
best model: gradient_boosted_stumps_200_lr_0_03
model type: gradient_boosted_regression_trees
R2: 0.0995
MAE: 159,572 nanoton
RMSE: 214,449 nanoton
baseline linear regression R2: -0.0051
R2 improvement vs baseline: +0.1046
```

Rolling backtest 기준:

```text
rolling best model: gradient_boosted_stumps_200_lr_0_03
mean R2: 0.0154
mean MAE: 155,372 nanoton
mean RMSE: 202,767 nanoton
folds: 8
```

해석:

```text
비선형 모델이 단일 holdout과 rolling backtest 평균 모두에서 1위입니다.
다만 rolling mean R2가 0.0154라서 예측력이 아직 강하다고 보기는 어렵습니다.
현재 모델은 "개선된 후보 모델"이지 "운영 신뢰도가 높은 확정 모델"은 아닙니다.
```

## 핵심 파일 설명

### raw_transactions.csv

거래 1건이 1행인 원시 거래 데이터입니다. 중복 제거 기준은 `hash + lt`입니다.

주요 컬럼:

```text
hash
now
account
lt
total_fees
compute_gas_used
compute_gas_fees
storage_fees_collected
total_action_fees
total_fwd_fees
vm_steps
msgs_created
out_msg_count
transaction_value
compute_success
action_success
aborted
```

### hourly_features.csv

모델 학습용 시간별 feature 테이블입니다.

포함 feature:

```text
tx_count
unique_accounts
avg_total_fee
median_total_fee
p90_total_fee
std_total_fee
avg_gas_used
avg_compute_fee
avg_storage_fee
avg_action_fee
avg_forward_fee
failed_tx_ratio
compute_success_ratio
action_success_ratio
fee_lag_1h / 3h / 6h / 12h / 24h
rolling_avg_fee_3h / 6h / 12h / 24h
rolling_std_fee_6h / 24h
fee_change_1h / 3h / 6h / 12h / 24h
tx_count_change_1h / 3h / 6h / 24h
gas_used_change_1h / 3h / 6h / 24h
p90_fee_change_1h / 3h / 6h / 24h
same_hour_prev_day_fee
hour_sin / hour_cos
day_sin / day_cos
target_next_hour_avg_fee
```

### predictions.csv

다음 24시간 평균 수수료 예측 결과입니다.

주요 컬럼:

```text
forecast_generated_at
forecast_hour
horizon_hours
predicted_avg_total_fee
predicted_avg_total_fee_ton
model_name
model_trained_at_utc
```

### models/model_comparison.csv

단일 chronological holdout 기준 모델 비교표입니다.

### models/rolling_backtest.csv

최근 8개 24시간 구간을 대상으로 한 expanding-window rolling backtest 요약입니다.

주요 컬럼:

```text
model_name
mean_r2
median_r2
std_r2
min_r2
max_r2
mean_mae
mean_rmse
r2_win_count
folds
```

### models/rolling_backtest_folds.csv

fold별 상세 backtest 결과입니다. 각 fold는 과거 구간으로 학습하고 다음 24시간을 테스트합니다.

### models/best_model.json

현재 선택된 best model입니다. `src/generate_forecast.py`는 기본적으로 이 파일을 사용합니다. 현재 best model은 비선형 tree ensemble이므로 JSON 안에 tree 구조가 저장됩니다.

### actual_vs_predicted.csv

테스트 구간에서 실제 다음 시간 평균 수수료와 예측 수수료를 비교한 파일입니다.

### docs/model_evaluation_report.md

모델 평가 요약 리포트입니다. 단일 holdout 결과와 rolling backtest 결과를 같이 기록합니다.

### docs/visualizations.md 와 docs/figures/

`docs/visualizations.md`는 생성된 SVG 그래프를 모아둔 문서이고, `docs/figures/`는 그래프 파일이 저장되는 폴더입니다.

현재 생성되는 그래프:

```text
hourly_fee_trend.svg
fee_distribution.svg
network_activity_trend.svg
model_r2_comparison.svg
rolling_backtest_r2_comparison.svg
model_mae_comparison.svg
actual_vs_predicted.svg
forecast_next_24h.svg
```

## 주요 스크립트

### src/update_data.py

TON Center API에서 거래 데이터를 수집하고 `raw_transactions.csv`를 업데이트합니다. 대량 backfill에는 `--stream` 옵션을 사용합니다.

### src/build_features.py

`raw_transactions.csv`를 시간별로 집계해서 `hourly_features.csv`를 만듭니다.

### src/train_model.py

모델을 학습하고 비교합니다.

현재 비교하는 모델:

```text
linear_regression
linear_regression_log1p_target
ridge_alpha_1
ridge_alpha_10
ridge_alpha_100
ridge_alpha_1_log1p_target
ridge_alpha_10_log1p_target
ridge_alpha_100_log1p_target
gradient_boosted_stumps_50_lr_0_05
gradient_boosted_stumps_100_lr_0_05
gradient_boosted_stumps_200_lr_0_03
gradient_boosted_trees_depth_3_50_lr_0_1
```

출력:

```text
models/best_model.json
models/model_metrics.json
models/model_comparison.csv
models/rolling_backtest.csv
models/rolling_backtest_folds.csv
models/feature_importance.csv
models/model_coefficients.csv
actual_vs_predicted.csv
docs/model_evaluation_report.md
```

### src/generate_forecast.py

`models/best_model.json`을 사용해서 다음 24시간 예측을 생성합니다.

### scripts/generate_charts.py

CSV 결과를 SVG 그래프로 생성합니다. 별도 plotting 라이브러리 없이 동작합니다.

### src/telegram_bot.py

저장된 결과 파일을 읽어서 Telegram 챗봇 대시보드로 보여줍니다. Telegram 요청 안에서 모델을 재학습하거나 CSV/JSON 결과 파일을 수정하지 않습니다.

실행:

```bash
cd /Users/changhyuklim/ton_fee_prediction
export TELEGRAM_BOT_TOKEN="your_token_here"
python3 src/telegram_bot.py
```

로컬 검증:

```bash
python3 -m py_compile src/telegram_bot.py
python3 src/telegram_bot.py --validate
```

주요 명령어:

```text
/summary
/forecast
/status
/besttime
/model
/compare
/backtest
/quality
/charts
```

자세한 설명은 `docs/telegram_bot.md`를 참고하세요. Telegram bot token은 환경변수에서만 읽고 코드나 문서에 저장하지 마세요.

### Netlify Telegram webhook

Mac 터미널을 계속 켜두지 않고 24시간 운영하려면 Netlify Function webhook을 사용합니다.

추가된 파일:

```text
netlify.toml
netlify/functions/telegram-webhook.mts
package.json
package-lock.json
tsconfig.json
```

파일 역할:

```text
src/telegram_bot.py
- 로컬 polling 방식 Telegram 봇입니다.
- Mac이나 VPS에서 프로세스를 계속 켜둘 때 사용합니다.

netlify/functions/telegram-webhook.mts
- Netlify에서 24시간 동작하는 Telegram webhook 함수입니다.
- Telegram POST update를 받아 dashboard 응답을 보냅니다.

netlify.toml
- Netlify 배포 설정입니다.
- 함수에 포함할 predictions.csv, hourly_features.csv, model 결과 파일, docs/figures 파일을 지정합니다.
- raw_transactions.csv는 포함하지 않습니다.

package.json / package-lock.json
- Netlify Function TypeScript 검증에 필요한 Node dependency와 npm script를 관리합니다.

tsconfig.json
- Netlify Function TypeScript 컴파일 설정입니다.

docs/telegram_bot.md
- 로컬 실행, Netlify 배포, webhook 등록, 명령어, 보안 주의사항을 정리한 상세 설명서입니다.

src/refresh_forecast_outputs.py
- GitHub Actions에서 사용하는 자동 refresh 스크립트입니다.
- GitHub Actions cache에서 Git에 commit되지 않는 raw_transactions.csv를 복원하고 증분 업데이트합니다.
- cache가 없거나 삭제된 첫 실행에서는 최근 3일 raw 데이터를 bootstrap합니다.
- 사용 가능한 raw hourly 집계를 기존 hourly_features.csv와 병합한 뒤 lag/rolling/target 컬럼을 다시 계산합니다.
- predictions.csv와 last_updated.json을 새로 갱신합니다.

.github/workflows/hourly_forecast_update.yml
- 매시간 최근 데이터, hourly_features.csv, predictions.csv, docs/figures/*.svg를 갱신합니다.

.github/workflows/daily_model_retrain.yml
- 하루 한 번 모델을 재학습하고 model 결과 파일, forecast, chart를 갱신합니다.

docs/automation_forecast_refresh.md
- Telegram /forecast가 자동으로 최신화되는 구조와 필요한 secret을 설명합니다.
```

Netlify 환경변수:

```text
TELEGRAM_BOT_TOKEN=BotFather에서 받은 토큰
TELEGRAM_WEBHOOK_SECRET=긴 랜덤 문자열(선택이지만 권장)
```

배포 후 webhook URL:

```text
https://ton-fee-forecast.netlify.app/telegram-webhook
```

Telegram webhook 등록:

```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_WEBHOOK_SECRET="a_long_random_secret"
export NETLIFY_BOT_URL="https://ton-fee-forecast.netlify.app/telegram-webhook"

curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=${NETLIFY_BOT_URL}" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

Netlify 함수 검증:

```bash
npm install
npm run check:netlify
```

같은 Telegram bot token으로 로컬 polling 봇과 Netlify webhook을 동시에 운영하지 마세요. Netlify로 운영할 때는 로컬 `src/telegram_bot.py` 프로세스를 중지하세요.

### 자동 forecast refresh

Telegram 사용자가 `/forecast`를 입력할 때 Telegram handler가 직접 데이터를 수집하거나 모델을 학습하지 않습니다. 대신 GitHub Actions가 백그라운드에서 output 파일을 갱신하고, Netlify가 새 파일을 포함해 다시 배포한 뒤, Telegram bot이 그 최신 배포 파일을 읽습니다.

흐름:

```text
GitHub Actions hourly schedule
-> GitHub Actions cache에서 raw_transactions.csv 복원
-> raw_transactions.csv 증분 업데이트
-> raw_transactions.csv를 다시 Actions cache에 저장
-> hourly_features.csv 병합/갱신
-> predictions.csv 재생성
-> chart 재생성
-> lightweight output만 GitHub에 commit
-> Netlify 자동 redeploy 또는 build hook 호출
-> Telegram /forecast가 최신 배포 파일 읽기
```

중요:

```text
raw_transactions.csv는 GitHub에 올리지 않습니다.
raw_transactions.csv는 Git commit에 포함하지 않고 GitHub Actions cache에만 저장합니다.
.automation_*.json 같은 임시 파일도 commit하지 않습니다.
Actions cache는 영구 데이터베이스가 아니므로 cache가 삭제되면 최근 3일 raw부터 다시 bootstrap합니다.
TON Center page limit에 걸린 구간의 tx_count/unique_accounts는 여전히 sampled activity로 해석해야 합니다.
```

필요한 GitHub Actions secret:

```text
TONCENTER_API_KEY
NETLIFY_BUILD_HOOK_URL  # Netlify가 GitHub에 직접 연결되어 있지 않을 때만 필요
```

Telegram에서 freshness 확인:

```text
/forecast
- forecast 생성 시각
- forecast 범위
- latest feature hour
- latest raw transaction timestamp
- stale/fresh 경고

/status
- 자동 업데이트 상태
- forecast age
- 최근 CI raw sample row 수
- known full raw row 수
```

## 기본 실행 명령어

프로젝트 폴더 이동:

```bash
cd /Users/changhyuklim/ton_fee_prediction
```

전체 재실행:

```bash
python3 src/build_features.py
python3 src/train_model.py
python3 src/generate_forecast.py
python3 scripts/generate_charts.py
```

데이터 업데이트까지 포함:

```bash
python3 src/update_data.py
python3 src/build_features.py
python3 src/train_model.py
python3 src/generate_forecast.py
python3 scripts/generate_charts.py
```

## 모델 비교 확인

단일 holdout 모델 비교:

```bash
python3 - <<'PY'
import pandas as pd

df = pd.read_csv("models/model_comparison.csv")
print(df[["model_name", "r2", "mae", "rmse", "mape"]].to_string(index=False))
PY
```

Rolling backtest 모델 비교:

```bash
python3 - <<'PY'
import pandas as pd

df = pd.read_csv("models/rolling_backtest.csv")
cols = ["model_name", "mean_r2", "median_r2", "mean_mae", "mean_rmse", "r2_win_count", "folds"]
print(df[cols].to_string(index=False))
PY
```

Fold별 승자 확인:

```bash
python3 - <<'PY'
import pandas as pd

df = pd.read_csv("models/rolling_backtest_folds.csv")
cols = ["fold", "winning_model_name", "test_start_hour", "test_end_hour"]
print(df[cols].drop_duplicates().to_string(index=False))
PY
```

## 예측 결과 확인

```bash
head -20 predictions.csv
```

## 그래프 확인

그래프 생성:

```bash
python3 scripts/generate_charts.py
```

그래프 파일 위치:

```text
docs/figures/
```

개별 그래프 열기:

```bash
open docs/figures/model_r2_comparison.svg
open docs/figures/rolling_backtest_r2_comparison.svg
open docs/figures/actual_vs_predicted.svg
open docs/figures/forecast_next_24h.svg
```

## 대량 백필 명령어

API 키는 `TONCENTER_API_KEY` 환경변수를 사용합니다. 키를 출력하지 마세요.

API 키가 zsh interactive 환경에 있을 때:

```bash
zsh -ic 'cd /Users/changhyuklim/ton_fee_prediction && python3 src/update_data.py --stream --start-date 2026-04-20T06:00:00Z --end-date 2026-04-21T06:00:00Z --limit 1000 --max-pages-per-window 5 --workchain 0 --sleep 0.02'
```

더 높은 데이터 밀도 실험:

```bash
--max-pages-per-window 10
```

주의:

```text
--stream은 .raw_transactions.csv.tmp를 사용해서 raw CSV를 다시 씁니다.
src/update_data.py 프로세스가 실행 중이면 같은 파일에 대해 다른 update_data.py를 동시에 실행하지 마세요.
```

실행 중 프로세스 확인:

```bash
ps aux | rg 'src/update_data.py'
ls -lh raw_transactions.csv .raw_transactions.csv.tmp last_updated.json 2>/dev/null || true
cat last_updated.json
```

## 데이터 검증 명령어

```bash
python3 - <<'PY'
import pandas as pd

raw = pd.read_csv("raw_transactions.csv", usecols=["hash", "lt", "now", "total_fees"])
hourly = pd.read_csv("hourly_features.csv")
pred = pd.read_csv("predictions.csv")
comparison = pd.read_csv("models/model_comparison.csv")
rolling = pd.read_csv("models/rolling_backtest.csv")

print("raw rows:", len(raw))
print("duplicates:", raw.duplicated(["hash", "lt"]).sum())
print("hourly rows:", len(hourly))
print("prediction rows:", len(pred))
print("raw range:", pd.to_datetime(raw["now"], unit="s", utc=True).min(), pd.to_datetime(raw["now"], unit="s", utc=True).max())
print("prediction range:", pred["forecast_hour"].min(), pred["forecast_hour"].max())
print("holdout best:", comparison.iloc[0]["model_name"], comparison.iloc[0]["r2"])
print("rolling best:", rolling.iloc[0]["model_name"], rolling.iloc[0]["mean_r2"])
PY
```

## 앞으로 할 일

우선순위:

```text
1. --max-pages-per-window 10으로 주요 구간 고밀도 재수집
2. rolling backtest fold 수와 기간을 더 늘려 안정성 확인
3. 평균 수수료 외 median/p90 target도 별도 예측
4. forecast에 uncertainty range 추가
5. 이상치 처리 또는 trimmed mean target 실험
6. 대시보드 UI 구현
```

현재 결론:

```text
데이터 파이프라인은 정상 동작합니다.
비선형 모델이 기존 선형/Ridge 모델보다 성능이 좋습니다.
하지만 rolling backtest 평균 R2가 낮으므로, 모델 신뢰도 개선은 아직 필요합니다.
```

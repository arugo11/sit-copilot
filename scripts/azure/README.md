# Azure safety scripts

Students サブスクリプションに再配備する時の最低限の運用コマンドです。

## 1. Provider 登録

```bash
./scripts/azure/register_students_providers.sh 4c170a0d-3e6d-42a0-b941-533e4f44e729
```

## 2. Container App を safe mode に固定

```bash
./scripts/azure/set_students_safe_env.sh \
  4c170a0d-3e6d-42a0-b941-533e4f44e729 \
  sit-copilot \
  <container-app-name>
```

## 3. Container App を public demo mode に固定

```bash
./scripts/azure/set_students_demo_env.sh \
  4c170a0d-3e6d-42a0-b941-533e4f44e729 \
  sit-copilot \
  <container-app-name>
```

## 4. 現在の cost-sensitive flag を確認

```bash
./scripts/azure/show_cost_flags.sh \
  4c170a0d-3e6d-42a0-b941-533e4f44e729 \
  sit-copilot \
  <container-app-name>
```

## 5. Subscription budget を 50/80/100% 通知つきで作成

```bash
./scripts/azure/create_students_budget.sh \
  4c170a0d-3e6d-42a0-b941-533e4f44e729 \
  sit-copilot-students-monthly \
  30 \
  your.name@example.edu
```

Action Group を連携したい場合は 5 引数目に Azure resource id を CSV で渡します。

## 6. Log Analytics の daily cap / retention を最小化

```bash
./scripts/azure/set_log_analytics_limits.sh \
  4c170a0d-3e6d-42a0-b941-533e4f44e729 \
  sit-copilot \
  <workspace-name>
```

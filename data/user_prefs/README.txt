# data 目录（GitHub 安全上传版）

本目录是给 GitHub 仓库使用的安全版 data 包。

## 已保留
- user_prefs 中的模板与规则文件
- 空的 histories / logs / runtime / workspace 目录结构

## 已移除
- 当前运行状态
- 当前草稿与回复中间文件
- 日志
- 历史记录
- 本机 GPT-SoVITS 路径与 Python 路径
- 最近成功路径
- 私钥 / token / 本机隐私数据

## 首次运行建议
1. 将 `machine_profile.template.json` 复制或重命名为 `machine_profile.json`
2. 按本机环境填写 Ollama / GPT-SoVITS 路径
3. 其他模板文件可按需复制为正式配置文件

## 建议不要上传到 GitHub 的真实文件
- data/runtime/*
- data/workspace/*
- data/logs/*
- data/histories/*
- data/user_prefs/machine_profile.json
- data/user_prefs/desktop_provider_profiles.json

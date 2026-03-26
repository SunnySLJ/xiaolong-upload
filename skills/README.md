# Skills 目录说明

## ⚠️ 重要

本目录 (`skills/`) 仅作为 **备份和参考**，**不直接使用**。

## 实际调用的 Skill

所有技能调用都使用 **OpenClaw 系统 Skill**：

```
~/.local/node/lib/node_modules/openclaw/skills/video-publish-flow/SKILL.md
```

## 本目录结构

```
skills/
└── video-publish-flow/
    └── SKILL.md  # 备份文件，与系统 Skill 同步
```

## 更新流程

修改 Skill 时：
1. 编辑系统 Skill: `~/.local/node/lib/node_modules/openclaw/skills/video-publish-flow/SKILL.md`
2. 同步到本目录：`cp ~/.local/node/lib/node_modules/openclaw/skills/video-publish-flow/SKILL.md ~/.openclaw/workspace/xiaolong-upload/skills/video-publish-flow/`

## 为什么这样设计？

- **系统 Skill**：OpenClaw 直接加载，真正生效
- **本目录**：作为项目文档和备份，方便查看和版本管理

---
*由虾王 🦐 维护*

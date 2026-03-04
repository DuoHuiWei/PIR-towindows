# Git 标准提交合并流程文档
![](https://cdn.nlark.com/yuque/0/2025/jpeg/52905985/1763606209411-701c6150-8702-415a-9b98-ef3ea9635a6b.jpeg)

## 项目信息
+ **远端仓库**: `origin` ([https://github.com/blackdesert5410/CE-PIR.git](https://github.com/blackdesert5410/CE-PIR.git))
+ **默认分支**: `main` (生产环境)
+ **开发分支**: `develop` (开发环境)
+ **功能分支**: `feature` (功能开发)
+ **所有远端分支**: 
    - `origin/main` (主分支)
    - `origin/develop` (开发分支)
    - `origin/feature` (功能分支)

## 一、查看分支信息
### 查看本地分支
```bash
git branch
```

### 查看远端分支
```bash
git branch -r
```

### 查看所有分支（本地+远端）
```bash
git branch -a
```

### 查看远端仓库信息
```bash
git remote -v
```

### 获取最新的远端分支信息
```bash
git fetch origin
```

## 二、标准提交流程
### 1. 检查当前状态
```bash
# 查看当前工作区状态
git status

# 查看当前分支
git branch
```

### 2. 拉取最新代码
```bash
# 从远端拉取最新代码（推荐）
git pull origin main

# 或者先fetch再merge
git fetch origin
git merge origin/main
```

### 3. 创建功能分支（可选，推荐）
```bash
# 创建并切换到新分支
git checkout -b feature/your-feature-name

# 或者使用新语法
git switch -c feature/your-feature-name
```

### 4. 添加修改
```bash
# 添加所有修改的文件
git add .

# 或者添加指定文件
git add <file1> <file2>

# 查看将要提交的更改
git status
```

### 5. 提交更改
```bash
# 提交更改（使用清晰的提交信息）
git commit -m "feat: 添加新功能描述"

# 提交信息规范建议：
# - feat: 新功能
# - fix: 修复bug
# - docs: 文档更新
# - style: 代码格式调整（不影响功能）
# - refactor: 代码重构
# - test: 测试相关
# - chore: 构建/工具链相关
```

### 6. 推送代码
```bash
# 如果是在功能分支
git push origin feature/your-feature-name

# 如果是在主分支
git push origin main
```

## 三、多分支工作流程
### 分支策略说明
本项目采用多分支开发策略：

+ `main`: 主分支，用于生产环境，保持稳定
+ `develop`: 开发分支，用于集成开发中的功能
+ `feature`: 功能分支，用于开发新功能

### 典型工作流程
#### 1. 从 develop 分支创建功能分支
```bash
# 切换到 develop 分支
git checkout develop

# 拉取最新的 develop 代码
git pull origin develop

# 从 develop 创建功能分支
git checkout -b feature/your-feature-name
```

#### 2. 在功能分支上开发
```bash
# 进行开发工作
# ... 编写代码 ...

# 提交更改
git add .
git commit -m "feat: 新功能描述"

# 推送到远端
git push origin feature/your-feature-name
```

#### 3. 合并到 develop 分支
```bash
# 切换到 develop 分支
git checkout develop

# 拉取最新代码
git pull origin develop

# 合并功能分支
git merge feature/your-feature-name

# 推送到远端
git push origin develop
```

#### 4. 从 develop 合并到 main（发布）
```bash
# 切换到 main 分支
git checkout main

# 拉取最新代码
git pull origin main

# 合并 develop 分支
git merge develop

# 推送到远端
git push origin main
```

#### 5. 删除本地功能分支（可选）
```bash
git branch -d feature/your-feature-name
```

### 切换和同步分支
```bash
# 切换到 develop 分支
git checkout develop
# 或使用新语法
git switch develop

# 拉取并同步 develop 分支
git pull origin develop

# 切换到 feature 分支
git checkout feature
git pull origin feature

# 查看分支状态
git status
```

## 四、标准合并流程
### 通过 Pull Request 合并（推荐，适用于团队协作）
#### 1. 推送功能分支到远端
```bash
# 在功能分支上
git push origin feature/your-feature-name
```

#### 2. 在 GitHub 上创建 Pull Request
+ 访问仓库页面
+ 点击 "New Pull Request"
+ 选择 `feature/your-feature-name` -> `main`
+ 填写 PR 描述
+ 提交 PR

#### 3. 代码审查后合并
+ 在 GitHub 上审查代码
+ 通过后点击 "Merge pull request"
+ 选择合并方式（Merge commit / Squash and merge / Rebase and merge）

#### 4. 更新本地主分支
```bash
# 切换到主分支
git checkout main

# 拉取合并后的最新代码
git pull origin main

# 删除本地功能分支
git branch -d feature/your-feature-name

# 删除远端功能分支（如果已合并）
git push origin --delete feature/your-feature-name
```





## 五、常用操作
### 查看提交历史
```bash
# 查看提交历史
git log

# 查看简洁的提交历史
git log --oneline

# 查看图形化提交历史
git log --graph --oneline --all
```

### 撤销操作
```bash
# 撤销工作区的修改（未add）
git checkout -- <file>

# 或者使用新语法
git restore <file>

# 撤销已add但未commit的文件
git reset HEAD <file>

# 或者使用新语法
git restore --staged <file>

# 撤销最后一次commit（保留修改）
git reset --soft HEAD~1

# 撤销最后一次commit（不保留修改）
git reset --hard HEAD~1
```

### 查看差异
```bash
# 查看工作区与暂存区的差异
git diff

# 查看暂存区与最后一次commit的差异
git diff --staged

# 查看与远端分支的差异
git diff origin/main
```

### 同步远端分支
```bash
# 获取远端所有分支的最新信息
git fetch origin

# 获取并合并远端分支
git pull origin main
git pull origin develop
git pull origin feature

# 强制同步（谨慎使用）
git fetch origin
git reset --hard origin/main        # 同步 main 分支
git reset --hard origin/develop     # 同步 develop 分支
git reset --hard origin/feature     # 同步 feature 分支
```

### 创建和删除分支
```bash
# 创建本地分支并跟踪远端分支
git checkout -b develop origin/develop
git checkout -b feature origin/feature

# 删除本地分支
git branch -d branch-name           # 删除已合并的分支
git branch -D branch-name           # 强制删除分支

# 删除远端分支
git push origin --delete branch-name
```

## 六、冲突解决
### 1. 拉取时出现冲突
```bash
# 拉取时如果有冲突
git pull origin main

# 查看冲突文件
git status

# 手动解决冲突后
git add <冲突文件>
git commit -m "resolve: 解决合并冲突"
```

### 2. 合并时出现冲突
```bash
# 合并时如果有冲突
git merge feature/your-feature-name

# 查看冲突文件
git status

# 手动编辑冲突文件，解决冲突标记（<<<<<<, ======, >>>>>>）

# 标记冲突已解决
git add <冲突文件>
git commit -m "resolve: 解决合并冲突"
```

## 七、最佳实践
1. **提交前先拉取**: 在提交前先 `git pull` 确保代码是最新的

## 八、快速参考命令
```bash
# 完整工作流程（多分支开发模式）
# 1. 从 develop 创建功能分支
git checkout develop                 # 切换到开发分支
git pull origin develop              # 拉取最新代码
git checkout -b feature/new-feature  # 创建功能分支

# 2. 在功能分支上开发
# ... 进行开发 ...
git add .                            # 添加修改
git commit -m "feat: 新功能"         # 提交
git push origin feature/new-feature  # 推送功能分支

# 3. 合并到 develop（通过 PR 或直接合并）
git checkout develop                 # 切换到开发分支
git pull origin develop              # 拉取最新代码
git merge feature/new-feature        # 合并功能分支
git push origin develop              # 推送到开发分支

# 4. 从 develop 合并到 main（发布）
git checkout main                    # 切换到主分支
git pull origin main                 # 拉取最新代码
git merge develop                    # 合并开发分支
git push origin main                 # 推送到主分支

# 5. 清理分支
git branch -d feature/new-feature    # 删除本地功能分支
git push origin --delete feature/new-feature  # 删除远端功能分支

# 完整工作流程（直接提交到主分支 - 不推荐）
git checkout main                    # 切换到主分支
git pull origin main                 # 拉取最新代码
# ... 进行开发 ...
git add .                            # 添加修改
git commit -m "feat: 新功能"         # 提交
git push origin main                 # 推送到主分支
```

## 九、当前项目分支操作示例
### 切换到 develop 分支
```bash
# 如果本地没有 develop 分支，先获取远端分支
git fetch origin

# 创建本地 develop 分支并跟踪远端
git checkout -b develop origin/develop

# 如果本地已有 develop 分支，直接切换
git checkout develop

# 拉取最新代码
git pull origin develop
```

### 切换到 feature 分支
```bash
# 如果本地没有 feature 分支，先获取远端分支
git fetch origin

# 创建本地 feature 分支并跟踪远端
git checkout -b feature origin/feature

# 如果本地已有 feature 分支，直接切换
git checkout feature

# 拉取最新代码
git pull origin feature
```

### 查看分支状态
```bash
# 查看所有分支的提交状态
git log --oneline --graph --all --decorate

# 查看各分支与 main 的差异
git log main..develop
git log main..feature

# 查看分支的提交数量
git rev-list --count main..develop
git rev-list --count main..feature
```

### 同步所有分支
```bash
# 获取所有远端分支的最新信息
git fetch origin

# 同步 main 分支
git checkout main
git pull origin main

# 同步 develop 分支
git checkout develop
git pull origin develop

# 同步 feature 分支
git checkout feature
git pull origin feature
```

## 十、注意事项
⚠️ **警告命令**（谨慎使用）:

+ `git reset --hard`: 会丢失未提交的修改
+ `git push --force`: 会覆盖远端历史，可能影响其他协作者
+ `git clean -fd`: 会删除未跟踪的文件

✅ **安全操作**:

+ 提交前使用 `git status` 检查状态
+ 使用 `git diff` 查看将要提交的更改
+ 重要修改前先备份或创建分支

---

**最后更新**: 2025年11月  
**维护者**: wizard


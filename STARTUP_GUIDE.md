# Linker Mind 项目启动指南

**项目类型**: Flask Web应用
**启动入口**: `run.py`

---

## 📋 前置检查清单

### 1. 环境要求

**必需软件**:
- Python 3.9+
- PostgreSQL 12+
- pip (Python包管理器)

**推荐工具**:
- VS Code / PyCharm（IDE）
- Postman / curl（API测试）
- pgAdmin / DBeaver（数据库管理）

### 2. 配置检查

**环境变量验证**:
```bash
# 检查.env文件是否存在
ls -la .env

# 检查必需的环境变量
grep -E "FIRECRAWL_API_KEY|DEEPSEEK_API_KEY|DATABASE_URL" .env
```

**必需配置项**:
- `DATABASE_URL` - PostgreSQL连接字符串
- `FIRECRAWL_API_KEY` - 网页内容提取
- `DEEPSEEK_API_KEY` - AI分析（可选）
- `SECRET_KEY` - Flask密钥

---

## 🚀 启动方式

### 方式一：开发服务器（推荐）

```bash
# 基础启动
python3 run.py

# 指定主机和端口
python3 run.py --host 0.0.0.0 --port 8080

# 后台运行
nohup python3 run.py > app.log 2>&1 &
```

**预期输出**:
```
==================================================
Starting development server on http://127.0.0.1:5000
Press Ctrl+C to stop
==================================================
 * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
```

**访问地址**: http://localhost:5000

### 方式二：生产服务器

```bash
# 使用Gunicorn（推荐）
python3 run.py --prod --workers 4

# 或指定端口和主机
python3 run.py --prod --host 0.0.0.0 --port 8000 --workers 8
```

**Gunicorn配置**:
- `workers`: CPU核心数 × 2 + 1
- `worker_class`: sync（同步工作模式）
- `timeout`: 30秒
- `keepalive`: 2秒

### 方式三：数据库初始化

```bash
# 初始化数据库（首次部署）
python3 run.py --init

# 运行数据迁移（如有结构变更）
python3 run.py --migrate
```

**初始化流程**:
1. 创建数据库表结构
2. 导入初始数据（如有JSON数据）
3. 创建索引
4. 验证表创建

### 方式四：配置验证

```bash
# 验证环境配置
python3 config/validator.py

# 显示帮助信息
python3 run.py --help
```

---

## 🛠️ 常见启动问题

### 问题1：ModuleNotFoundError: No module named 'psycopg2'

**原因**: PostgreSQL驱动未安装
**解决方案**:
```bash
# macOS
python3 -m pip install psycopg2-binary

# Linux
sudo apt-get install python3-psycopg2
# 或
python3 -m pip install psycopg2-binary

# Windows
python3 -m pip install psycopg2-binary
```

### 问题2：connection to server at "localhost" failed

**原因**: PostgreSQL服务未启动
**解决方案**:
```bash
# macOS (使用Homebrew安装的PostgreSQL)
brew services start postgresql

# Linux (systemd)
sudo systemctl start postgresql

# 验证服务状态
brew services list | grep postgresql
# 或
sudo systemctl status postgresql

# 检查端口占用
lsof -i :5432
```

### 问题3：FIRECRAWL_API_KEY not configured

**原因**: 缺少API密钥配置
**解决方案**:
```bash
# 编辑.env文件
nano .env

# 添加以下内容
FIRECRAWL_API_KEY=fc-your-api-key-here
DEEPSEEK_API_KEY=sk-your-deepseek-key-here

# 或设置环境变量
export FIRECRAWL_API_KEY="fc-your-api-key-here"
```

### 问题4：数据库已存在错误

**原因**: 重复初始化数据库
**解决方案**:
```bash
# 连接数据库清理
python3 -c "
from database.db_interface import get_connection
db = get_connection()
db.execute('DROP SCHEMA public CASCADE')
print('已清空数据库')
"

# 重新初始化
python3 run.py --init
```

### 问题5：端口已被占用

**原因**: 上次运行未正常关闭
**解决方案**:
```bash
# 查找占用端口的进程
lsof -ti:5000

# 杀死进程
kill -9 <PID>

# 或使用不同端口
python3 run.py --port 5001
```

---

## 🔧 开发环境设置

### VS Code调试配置

**.vscode/launch.json**:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Flask",
            "type": "python",
            "request": "launch_app",
            "module": "run",
            "args": ["--host", "0.0.0.0", "--port", "5000"],
            "console": "integratedTerminal",
            "env": {
                "FLASK_DEBUG": "true",
                "LOG_LEVEL": "DEBUG"
            }
        }
    ]
}
```

### PyCharm运行配置

**Run Configuration**:
- Script: `run.py`
- Python interpreter: 项目虚拟环境
- Environment variables: 从.env文件加载
- Working directory: 项目根目录

---

## 📊 健康检查

### 启动前检查

```bash
# 检查数据库连接
python3 -c "
from database.db_interface import get_connection
try:
    db = get_connection()
    print('✅ 数据库连接正常')
    db.close()
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
"

# 检查PostgreSQL服务
pg_isready=$(pg_isready 2>/dev/null && echo "OK" || echo "FAILED")
echo "PostgreSQL状态: $pg_isready"

# 检查端口占用
if lsof -i:5000 -sTCP:LISTEN; then
    echo "端口5000已被占用"
else
    echo "端口5000可用"
```

### 运行时监控

**日志文件位置**:
```bash
# 应用日志（如果配置）
tail -f logs/app.log

# 系统日志（如果使用systemd）
journalctl -u postgresql -f

# Flask开发服务器日志
# 默认输出到终端
```

---

## 🎯 快速启动命令

### 首次部署

```bash
# 1. 安装依赖
python3 -m pip install -r requirements.txt

# 2. 配置环境
cp .env.example .env
nano .env  # 编辑配置

# 3. 初始化数据库
python3 run.py --init

# 4. 启动开发服务器
python3 run.py
```

### 日常开发

```bash
# 启动（前台运行）
python3 run.py

# 启动（后台运行）
nohup python3 run.py > dev.log 2>&1 &

# 查看日志
tail -f dev.log

# 停止服务
pkill -f "python.*run.py"
```

### 生产部署

```bash
# 启动生产服务
python3 run.py --prod --workers 4

# 检查服务状态
curl http://localhost:5000/health

# 查看Gunicorn进程
ps aux | grep gunicorn
```

---

## 📝 配置参考

### .env 文件示例

```bash
# 应用配置
SECRET_KEY=dev-secret-key-change-in-production
FLASK_DEBUG=true
LOG_LEVEL=INFO

# 数据库配置
DATABASE_URL=postgresql://postgres:password@localhost:5432/linker_mind
DB_TYPE=postgresql
PGHOST=localhost
PGPORT=5432
PGDATABASE=linker_mind
PGUSER=postgres
PGPASSWORD=your_secure_password

# API配置
FIRECRAWL_API_KEY=fc-your-key-here
DEEPSEEK_API_KEY=sk-your-key-here
MAX_RETRIES=3
FIRECRAWL_TIMEOUT=30
```

### 数据库连接字符串格式

```
postgresql://用户名:密码@主机:端口/数据库名
postgresql://postgres:mypass@localhost:5432/linker_mind

# 使用socket连接（本地）
postgresql:///var/run/postgresql/.s.PGSQL.5432/linker_mind

# 使用连接池
postgresql://?host=localhost&port=5432&dbname=linker_mind
```

---

## 🔄 更新与维护

### 代码更新后

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 更新依赖
python3 -m pip install -r requirements.txt

# 3. 重启服务
pkill -f "python.*run.py"
python3 run.py &
```

### 数据库迁移

```bash
# 创建迁移脚本
python3 database/migration_pg.py

# 验证迁移
python3 -c "
from database.db_interface import get_connection
db = get_connection()
tables = db.get_tables()
print(f'当前表: {tables}')
db.close()
"
```

---

## ✅ 启动成功标志

**看到以下输出表示启动成功**:
```
==================================================
Linker Mind - 学习与创作版
==================================================
Starting development server on http://127.0.0.1:5000
Press Ctrl+C to stop
---------------------------------------------------------
 * Serving Flask App "Linker Mind"
 * Debug mode: on
 * Running on http://127.0.0.1:5000
---------------------------------------------------------
```

**访问测试**:
```bash
# 测试API接口
curl http://localhost:5000/api/health

# 测试网页访问
curl http://localhost:5000/

# 查看API文档
curl http://localhost:5000/docs
```

---

*指南版本: v1.0*
*最后更新: 2025-02-15*

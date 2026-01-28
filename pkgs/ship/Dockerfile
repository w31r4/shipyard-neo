FROM python:3.13-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装构建依赖（临时）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    musl-dev \
    python3-dev \
    libffi-dev \
    libpng-dev \
    libjpeg-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===== 最终镜像 =====
FROM python:3.13-slim

WORKDIR /app

# 只安装运行时必需的依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 图像处理运行时库（Pillow / OpenCV headless）
    libpng16-16 \
    libjpeg62-turbo \
    libglib2.0-0 \
    # lxml 运行时库
    libxml2 \
    libxslt1.1 \
    # 字体显示
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    # 网络工具
    net-tools \
    # 用户管理工具
    sudo \
    passwd \
    adduser \
    # Node.js 安装需要的工具
    curl \
    gnupg \
    git \
    # 常用文本编辑器和工具（方便终端直连调试）
    vim-tiny \
    nano \
    less \
    procps \
    htop \
    && rm -rf /var/lib/apt/lists/*

# 从builder阶段复制Python包
COPY --from=builder /install /usr/local

# 安装 Node.js (LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g pnpm vercel \
    && npm cache clean --force

# 创建固定用户 shipyard（UID 1000）和 workspace 目录
RUN groupadd -g 1000 shipyard \
    && useradd -u 1000 -g shipyard -d /workspace -s /bin/bash shipyard \
    && mkdir -p /workspace \
    && chown shipyard:shipyard /workspace \
    && chmod 755 /workspace

# 配置 sudo（允许 root 无密码执行 sudo，用于切换到 shipyard 用户）
RUN echo "root ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers \
    && echo "Defaults:root !requiretty" >> /etc/sudoers \
    && echo "shipyard ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# 创建 .bashrc（login shell 时自动 cd 到 /workspace）
RUN echo '# Basic shell configuration for shipyard user' > /workspace/.bashrc \
    && echo "export PS1='\\u@shipyard:\\w\\$ '" >> /workspace/.bashrc \
    && echo 'export PATH=/usr/local/bin:/usr/bin:/bin' >> /workspace/.bashrc \
    && echo 'export HOME=/workspace' >> /workspace/.bashrc \
    && echo 'cd /workspace' >> /workspace/.bashrc \
    && chown shipyard:shipyard /workspace/.bashrc \
    && chmod 644 /workspace/.bashrc

# 复制项目文件
COPY . .

# 设置入口脚本权限
RUN chmod +x /app/entrypoint.sh

# 暴露端口
EXPOSE 8123

# 入口脚本：修复 workspace 权限后启动应用
ENTRYPOINT ["/app/entrypoint.sh"]

# 启动命令（以 root 运行 FastAPI，内部通过 sudo 切换到 shipyard 执行命令）
CMD ["python", "run.py"]

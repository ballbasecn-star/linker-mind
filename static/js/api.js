/**
 * Linker Mind API Client
 *
 * 统一的 API 调用客户端，提供简洁的接口与后端服务层交互
 */

class LinkerMindAPI {
    constructor() {
        this.baseURL = '';
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
    }

    /**
     * 通用请求方法
     */
    async request(url, options = {}) {
        const config = {
            ...options,
            headers: {
                ...this.defaultHeaders,
                ...options.headers
            }
        };

        try {
            const response = await fetch(this.baseURL + url, config);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Request failed');
            }

            return data.data || data;
        } catch (error) {
            console.error(`API Error [${url}]:`, error);
            throw error;
        }
    }

    async get(url, options = {}) {
        return this.request(url, { ...options, method: 'GET' });
    }

    async post(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(url, data, options = {}) {
        return this.request(url, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(url, options = {}) {
        return this.request(url, { ...options, method: 'DELETE' });
    }

    // ==================== Content API ====================

    /**
     * 处理 URL 并保存内容
     */
    async processURL(url, enableAI = true) {
        return this.post('/api/process', { url, enable_ai: enableAI });
    }

    /**
     * 获取内容列表
     */
    async getContents(filters = {}) {
        const params = new URLSearchParams();
        if (filters.contentType) params.append('content_type', filters.contentType);
        if (filters.sourceType) params.append('source_type', filters.sourceType);
        if (filters.tag) params.append('tag', filters.tag);
        if (filters.favorited !== undefined) params.append('favorited', filters.favorited);
        if (filters.sortBy) params.append('sort_by', filters.sortBy);
        if (filters.sortOrder) params.append('sort_order', filters.sortOrder);
        if (filters.page) params.append('page', filters.page);
        if (filters.pageSize) params.append('page_size', filters.pageSize);

        return this.get(`/api/contents?${params}`);
    }

    /**
     * 获取内容详情
     */
    async getContent(contentId) {
        return this.get(`/api/contents/${contentId}`);
    }

    /**
     * 更新内容
     */
    async updateContent(contentId, data) {
        return this.put(`/api/contents/${contentId}`, data);
    }

    /**
     * 切换收藏状态
     */
    async toggleFavorite(contentId) {
        return this.post(`/api/contents/${contentId}/favorite`);
    }

    /**
     * 切换归档状态
     */
    async toggleArchive(contentId) {
        return this.post(`/api/contents/${contentId}/archive`);
    }

    /**
     * 更新阅读进度
     */
    async updateReadingProgress(contentId, progress) {
        return this.put(`/api/contents/${contentId}/reading-progress`, { progress });
    }

    // ==================== Inbox API ====================

    /**
     * 添加到收件箱
     */
    async addToInbox(rawInput, options = {}) {
        return this.post('/api/inbox', {
            raw_input: rawInput,
            source_type: options.sourceType,
            title: options.title,
            url: options.url,
            quick_tags: options.tags,
            priority: options.priority,
            due_date: options.dueDate
        });
    }

    /**
     * 获取收件箱列表
     */
    async getInbox(status = 'pending', includeSnoozed = false, limit = 50) {
        const params = new URLSearchParams();
        params.append('status', status);
        params.append('include_snoozed', includeSnoozed);
        params.append('limit', limit);

        return this.get(`/api/inbox?${params}`);
    }

    /**
     * 处理收件箱项目
     */
    async processInboxItem(itemId, action, options = {}) {
        return this.put(`/api/inbox/${itemId}/process`, {
            action,
            content_id: options.contentId,
            snooze_until: options.snoozeUntil
        });
    }

    /**
     * 获取收件箱统计
     */
    async getInboxStats() {
        return this.get('/api/inbox/stats');
    }

    // ==================== Node API (PARA) ====================

    /**
     * 获取节点列表
     */
    async getNodes(filters = {}) {
        const params = new URLSearchParams();
        if (filters.type) params.append('type', filters.type);
        if (filters.status) params.append('status', filters.status);
        if (filters.limit) params.append('limit', filters.limit);

        return this.get(`/api/nodes?${params}`);
    }

    /**
     * 获取节点详情
     */
    async getNode(nodeId) {
        return this.get(`/api/nodes/${nodeId}`);
    }

    /**
     * 创建节点
     */
    async createNode(data) {
        return this.post('/api/nodes', data);
    }

    /**
     * 更新节点
     */
    async updateNode(nodeId, data) {
        return this.put(`/api/nodes/${nodeId}`, data);
    }

    /**
     * 删除节点
     */
    async deleteNode(nodeId, cascade = false) {
        return this.delete(`/api/nodes/${nodeId}?cascade=${cascade}`);
    }

    /**
     * 获取节点树
     */
    async getNodeTree(rootId = null, maxDepth = 3) {
        const params = new URLSearchParams();
        params.append('max_depth', maxDepth);
        if (rootId) params.append('root_id', rootId);

        return this.get(`/api/nodes/tree?${params}`);
    }

    /**
     * 添加内容到节点
     */
    async addContentToNode(nodeId, contentId, notes = '') {
        return this.post(`/api/nodes/${nodeId}/contents`, {
            content_id: contentId,
            notes
        });
    }

    /**
     * 从节点移除内容
     */
    async removeContentFromNode(nodeId, contentId) {
        return this.delete(`/api/nodes/${nodeId}/contents/${contentId}`);
    }

    // ==================== Note API ====================

    /**
     * 获取笔记列表
     */
    async getNotes(filters = {}) {
        const params = new URLSearchParams();
        if (filters.contentId) params.append('content_id', filters.contentId);
        if (filters.noteType) params.append('note_type', filters.noteType);
        if (filters.limit) params.append('limit', filters.limit);

        return this.get(`/api/notes?${params}`);
    }

    /**
     * 创建笔记
     */
    async createNote(data) {
        return this.post('/api/notes', data);
    }

    /**
     * 获取渐进式总结
     */
    async getContentSummary(contentId) {
        return this.get(`/api/contents/${contentId}/summary`);
    }

    /**
     * 添加高亮 (第1层总结)
     */
    async addHighlight(contentId, text, color = 'yellow') {
        return this.post(`/api/contents/${contentId}/highlights`, {
            text,
            color
        });
    }

    /**
     * 加粗重点 (第2层总结)
     */
    async addBolded(contentId, text) {
        return this.post(`/api/contents/${contentId}/bolded`, { text });
    }

    /**
     * 添加超级笔记 (第3层总结)
     */
    async addSuperNote(contentId, text) {
        return this.post(`/api/contents/${contentId}/supernote`, { text });
    }

    /**
     * 添加个人总结 (第4层总结)
     */
    async addOwnWords(contentId, text) {
        return this.post(`/api/contents/${contentId}/own-words`, { text });
    }

    /**
     * 添加深度思考 (第5层总结)
     */
    async addInsight(contentId, text) {
        return this.post(`/api/contents/${contentId}/insight`, { text });
    }

    // ==================== Link API ====================

    /**
     * 创建链接
     */
    async createLink(sourceId, targetId, options = {}) {
        return this.post('/api/links', {
            source_id: sourceId,
            target_id: targetId,
            source_type: options.sourceType || 'content',
            target_type: options.targetType || 'content',
            link_type: options.linkType || 'RELATED',
            context: options.context,
            strength: options.strength || 1.0
        });
    }

    /**
     * 获取内容的链接
     */
    async getContentLinks(contentId) {
        return this.get(`/api/links/contents/${contentId}/links`);
    }

    /**
     * 获取反向链接
     */
    async getBacklinks(contentId) {
        return this.get(`/api/links/contents/${contentId}/backlinks`);
    }

    /**
     * 获取相关内容推荐
     */
    async getRelatedContent(contentId, limit = 10) {
        return this.get(`/api/links/contents/${contentId}/related?limit=${limit}`);
    }

    /**
     * 获取链接建议
     */
    async getLinkSuggestions(contentId, limit = 10) {
        return this.get(`/api/links/suggestions?content_id=${contentId}&limit=${limit}`);
    }

    // ==================== Session API (Learning) ====================

    /**
     * 开始学习会话
     */
    async startSession(contentId) {
        return this.post(`/api/sessions/contents/${contentId}/session`);
    }

    /**
     * 结束学习会话
     */
    async endSession(sessionId, data) {
        return this.put(`/api/sessions/${sessionId}`, data);
    }

    /**
     * 获取学习会话列表
     */
    async getSessions(contentId = null, limit = 50) {
        const params = new URLSearchParams();
        params.append('limit', limit);
        if (contentId) params.append('content_id', contentId);

        return this.get(`/api/sessions?${params}`);
    }

    /**
     * 获取待复习内容
     */
    async getDueReviews(limit = 20) {
        return this.get(`/api/sessions/reviews/due?limit=${limit}`);
    }

    /**
     * 提交复习
     */
    async submitReview(contentId, quality) {
        return this.post(`/api/sessions/reviews/${contentId}`, { quality });
    }

    /**
     * 获取学习统计
     */
    async getLearningStats(days = 30) {
        return this.get(`/api/sessions/stats/learning?days=${days}`);
    }

    // ==================== Skill API ====================

    /**
     * 获取技能列表
     */
    async getSkills(filters = {}) {
        const params = new URLSearchParams();
        if (filters.category) params.append('category', filters.category);
        if (filters.level) params.append('level', filters.level);
        if (filters.limit) params.append('limit', filters.limit);

        return this.get(`/api/skills?${params}`);
    }

    /**
     * 获取技能详情
     */
    async getSkill(skillId) {
        return this.get(`/api/skills/${skillId}`);
    }

    /**
     * 创建技能
     */
    async createSkill(data) {
        return this.post('/api/skills', data);
    }

    /**
     * 获取技能树
     */
    async getSkillTree(rootId = null) {
        const params = new URLSearchParams();
        if (rootId) params.append('root_id', rootId);

        return this.get(`/api/skills/tree?${params}`);
    }

    /**
     * 获取学习路径
     */
    async getLearningPath(skillId) {
        return this.get(`/api/skills/${skillId}/path`);
    }

    // ==================== Creation API ====================

    /**
     * 获取创作项目列表
     */
    async getCreations(filters = {}) {
        const params = new URLSearchParams();
        if (filters.status) params.append('status', filters.status);
        if (filters.projectType) params.append('project_type', filters.projectType);

        return this.get('/api/creations');
    }

    /**
     * 创建创作项目
     */
    async createCreation(data) {
        return this.post('/api/creations', data);
    }

    /**
     * 获取创作项目详情
     */
    async getCreation(projectId) {
        return this.get(`/api/creations/${projectId}`);
    }

    /**
     * 更新创作项目
     */
    async updateCreation(projectId, data) {
        return this.put(`/api/creations/${projectId}`, data);
    }

    /**
     * 生成大纲
     */
    async generateOutline(projectId) {
        return this.post(`/api/creations/${projectId}/outline`);
    }

    /**
     * 更新大纲
     */
    async updateOutline(projectId, outline) {
        return this.put(`/api/creations/${projectId}/outline`, { outline });
    }

    /**
     * 扩展章节
     */
    async expandSection(projectId, sectionId) {
        return this.post(`/api/creations/${projectId}/sections/${sectionId}`);
    }

    /**
     * 保存草稿
     */
    async saveDraft(projectId, content) {
        return this.put(`/api/creations/${projectId}/draft`, { content });
    }

    /**
     * 发布创作
     */
    async publishCreation(projectId, url) {
        return this.post(`/api/creations/${projectId}/publish`, { url });
    }

    /**
     * 获取引用列表
     */
    async getCitations(projectId, format = 'academic') {
        return this.get(`/api/creations/${projectId}/citations?format=${format}`);
    }

    /**
     * 发现内容缺口
     */
    async findGaps(projectId) {
        return this.get(`/api/creations/${projectId}/gaps`);
    }

    // ==================== Graph API ====================

    /**
     * 获取知识图谱数据
     */
    async getGraph(limit = 100, minWeight = 0.5) {
        return this.get(`/api/graph?limit=${limit}&min_weight=${minWeight}`);
    }

    /**
     * 获取主题聚类
     */
    async getTopicClusters(minSize = 3) {
        return this.get(`/api/graph/cluster?min_size=${minSize}`);
    }

    /**
     * 获取节点连接
     */
    async getNodeConnections(nodeId, depth = 2, maxNodes = 50) {
        return this.get(`/api/graph/connections/${nodeId}?depth=${depth}&max_nodes=${maxNodes}`);
    }

    /**
     * 获取图谱统计
     */
    async getGraphStats() {
        return this.get('/api/graph/stats');
    }

    // ==================== Search API ====================

    /**
     * 搜索内容
     */
    async search(query, filters = {}) {
        const params = new URLSearchParams();
        params.append('q', query);

        if (filters.types) params.append('types', filters.types.join(','));
        if (filters.tags) params.append('tags', filters.tags.join(','));
        if (filters.dateFrom) params.append('date_from', filters.dateFrom);
        if (filters.dateTo) params.append('date_to', filters.dateTo);
        if (filters.minQuality) params.append('min_quality', filters.minQuality);
        if (filters.favorited !== undefined) params.append('favorited', filters.favorited);
        if (filters.page) params.append('page', filters.page);
        if (filters.pageSize) params.append('page_size', filters.pageSize);

        return this.get(`/api/search?${params}`);
    }

    /**
     * 获取搜索建议
     */
    async getSearchSuggestions(query) {
        return this.get(`/api/search/suggestions?q=${encodeURIComponent(query)}`);
    }

    /**
     * 高级搜索
     */
    async advancedSearch(query, filters = {}) {
        return this.post('/api/search/advanced', {
            query,
            filters
        });
    }

    // ==================== Composite API ====================

    /**
     * 获取仪表盘数据
     */
    async getDashboard() {
        return this.get('/api/dashboard');
    }

    /**
     * 导出数据
     */
    async exportData(format = 'json', contentType = 'all') {
        const response = await fetch(`${this.baseURL}/api/export?format=${format}&content_type=${contentType}`);

        if (format === 'json') {
            return response.json();
        } else {
            return response.text();
        }
    }

    /**
     * 健康检查
     */
    async healthCheck() {
        return this.get('/api/health');
    }

    /**
     * 获取应用设置
     */
    async getSettings() {
        return this.get('/api/settings');
    }
}

// 创建全局实例
const api = new LinkerMindAPI();

// 导出到全局
window.LinkerMindAPI = LinkerMindAPI;
window.api = api;

#!/usr/bin/env python3
"""
测试AI写作闭环工作流
"""
import os
import sys

# 设置环境变量（测试用）
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/linker_mind')

from services.creation_service import CreationWorkshopService, CreationType, CreationStatus
from services.creation_assistant import AICreationAssistantService

def test_creation_service():
    """测试创建服务"""
    print("=" * 50)
    print("测试1: 创建服务")
    print("=" * 50)

    try:
        service = CreationWorkshopService()

        # 创建测试项目
        project = service.create(
            project_type=CreationType.ARTICLE,
            title="测试AI写作项目",
            brief="这是一个测试项目",
            word_count_goal=2000
        )

        print(f"✓ 创建项目成功: {project.id}")
        print(f"  标题: {project.title}")
        print(f"  状态: {project.status}")

        return project.id
    except Exception as e:
        print(f"✗ 创建项目失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_workflow_config():
    """测试工作流配置"""
    print("\n" + "=" * 50)
    print("测试2: 工作流配置")
    print("=" * 50)

    try:
        from services.creation_service import get_workflow_for_type, AI_WRITING_WORKFLOW

        # 测试文章工作流
        article_workflow = get_workflow_for_type('article')
        print(f"✓ 获取文章工作流成功")
        print(f"  步骤数: {len(article_workflow)}")

        for i, step in enumerate(article_workflow):
            print(f"  {i+1}. {step['step']} -> {step['status'].value}")

        # 测试视频脚本工作流
        video_workflow = get_workflow_for_type('video_script')
        print(f"✓ 获取视频脚本工作流成功")
        print(f"  步骤数: {len(video_workflow)}")

        return True
    except Exception as e:
        print(f"✗ 工作流配置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_assistant_llm():
    """测试AI助手LLM客户端"""
    print("\n" + "=" * 50)
    print("测试3: LLM客户端")
    print("=" * 50)

    try:
        from services.creation_assistant import get_llm_client

        client = get_llm_client()

        if client:
            print(f"✓ LLM客户端初始化成功")
            print(f"  API Key: {'已配置' if client.api_key else '未配置'}")
        else:
            print(f"⚠ LLM客户端未初始化 (可能缺少API Key)")

        return client
    except Exception as e:
        print(f"✗ LLM客户端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_generate_draft(project_id):
    """测试生成初稿"""
    print("\n" + "=" * 50)
    print("测试4: 生成初稿")
    print("=" * 50)

    try:
        assistant = AICreationAssistantService()
        result = assistant.generate_draft(project_id, target_words=500)

        if result:
            if 'error' in result:
                print(f"⚠ 生成初稿返回错误: {result['error']}")
            else:
                print(f"✓ 生成初稿成功")
                print(f"  字数: {result.get('word_count', 0)}")
                print(f"  来源数: {result.get('source_count', 0)}")
                if result.get('draft'):
                    print(f"  初稿前100字: {result['draft'][:100]}...")
        else:
            print(f"✗ 生成初稿返回None")

        return result
    except Exception as e:
        print(f"✗ 生成初稿失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_suggest_titles():
    """测试标题生成"""
    print("\n" + "=" * 50)
    print("测试5: 生成标题")
    print("=" * 50)

    try:
        assistant = AICreationAssistantService()

        # 先创建一个测试项目
        service = CreationWorkshopService()
        project = service.create(
            project_type=CreationType.ARTICLE,
            title="测试标题生成",
            brief="测试"
        )

        test_content = """
        这是一篇关于人工智能改变未来工作方式的文章。
        随着AI技术的发展，越来越多的工作将被自动化。
        但与此同时，新的工作机会也在不断产生。
        人类需要学会与AI协作，而不是与之竞争。
        """

        result = assistant.generate_titles(project.id, test_content, num_titles=3)

        if result:
            print(f"✓ 生成标题成功")
            for i, title in enumerate(result):
                print(f"  {i+1}. [{title.get('type', '常规')}] {title.get('title', '无')}")
        else:
            print(f"✗ 生成标题返回None")

        # 清理测试项目
        service.delete(project.id)

        return result
    except Exception as e:
        print(f"✗ 生成标题失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_structural_improvements():
    """测试结构优化"""
    print("\n" + "=" * 50)
    print("测试6: 结构优化建议")
    print("=" * 50)

    try:
        assistant = AICreationAssistantService()

        # 创建测试项目
        service = CreationWorkshopService()
        project = service.create(
            project_type=CreationType.ARTICLE,
            title="测试结构优化",
            brief="测试"
        )

        test_draft = """
        人工智能正在改变我们的生活方式。
        首先，AI可以帮助我们完成重复性的工作。
        其次，AI可以分析大量数据提供洞察。
        最后，AI可以创造新的内容和体验。
        总之，AI是未来发展的重要趋势。
        """

        result = assistant.suggest_structural_improvements(project.id, test_draft)

        if result:
            print(f"✓ 结构优化建议成功")
            print(f"  Version A: {result.get('version_a', {}).get('title', 'N/A')}")
            print(f"  Version B: {result.get('version_b', {}).get('title', 'N/A')}")
        else:
            print(f"✗ 结构优化返回None")

        # 清理
        service.delete(project.id)

        return result
    except Exception as e:
        print(f"✗ 结构优化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_platform_conversion():
    """测试平台格式转换"""
    print("\n" + "=" * 50)
    print("测试7: 平台格式转换")
    print("=" * 50)

    try:
        assistant = AICreationAssistantService()

        # 创建测试项目
        service = CreationWorkshopService()
        project = service.create(
            project_type=CreationType.ARTICLE,
            title="测试平台转换",
            brief="测试"
        )

        test_content = """
        人工智能正在改变我们的生活方式和工作方式。
        从智能助手到自动驾驶，AI的应用越来越广泛。
        未来，AI将成为我们生活中不可或缺的一部分。
        """

        result = assistant.convert_to_platform_format(project.id, test_content, 'x')

        if result:
            if 'error' in result:
                print(f"⚠ 平台转换返回错误: {result['error']}")
            else:
                print(f"✓ 平台转换成功")
                print(f"  平台: {result.get('platform', 'N/A')}")
                print(f"  内容前100字: {result.get('content', '')[:100]}...")
        else:
            print(f"✗ 平台转换返回None")

        # 清理
        service.delete(project.id)

        return result
    except Exception as e:
        print(f"✗ 平台转换失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_api_endpoints():
    """测试API端点"""
    print("\n" + "=" * 50)
    print("测试8: API端点")
    print("=" * 50)

    try:
        import requests

        base_url = "http://127.0.0.1:5000"

        # 测试1: 获取创作列表
        response = requests.get(f"{base_url}/api/creations")
        print(f"GET /api/creations: {response.status_code}")

        # 测试2: 创建创作项目
        response = requests.post(f"{base_url}/api/creations", json={
            "project_type": "article",
            "title": "API测试项目",
            "brief": "测试"
        })
        print(f"POST /api/creations: {response.status_code}")

        if response.status_code == 201:
            project_id = response.json().get('data', {}).get('id')
            print(f"  创建的项目ID: {project_id}")

            # 测试3: 获取项目详情
            response = requests.get(f"{base_url}/api/creations/{project_id}")
            print(f"GET /api/creations/{project_id}: {response.status_code}")

            # 测试4: 获取工作流
            response = requests.get(f"{base_url}/api/creations/{project_id}/workflow")
            print(f"GET /api/creations/{project_id}/workflow: {response.status_code}")
            if response.status_code == 200:
                workflow_data = response.json()
                print(f"  当前步骤: {workflow_data.get('data', {}).get('current_step')}")

            # 测试5: 生成初稿（会失败因为没有素材）
            response = requests.post(f"{base_url}/api/creations/{project_id}/generate-draft", json={
                "target_words": 500
            })
            print(f"POST /api/creations/{project_id}/generate-draft: {response.status_code}")
            if response.status_code != 200:
                print(f"  错误: {response.json().get('message', '未知')}")

            # 测试6: 改进结构（会失败因为没有草稿）
            response = requests.post(f"{base_url}/api/creations/{project_id}/improve-structure", json={
                "draft_content": "测试内容"
            })
            print(f"POST /api/creations/{project_id}/improve-structure: {response.status_code}")
            if response.status_code != 200:
                print(f"  错误: {response.json().get('message', '未知')}")

        return True
    except Exception as e:
        print(f"✗ API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("AI写作闭环工作流测试")
    print("=" * 50)

    # 运行所有测试
    test_workflow_config()
    test_ai_assistant_llm()

    # 创建测试项目
    project_id = test_creation_service()
    if project_id:
        test_generate_draft(project_id)

    test_suggest_titles()
    test_structural_improvements()
    test_platform_conversion()

    # 测试API
    test_api_endpoints()

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()

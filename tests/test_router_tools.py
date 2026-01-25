# tests/test_router_tools.py

from modules import router_tools

def test_run_tests_tool():
    assert router_tools.run_tests.func("dev") == "/utils dev --run-tests-dev"
    assert router_tools.run_tests.func("all") == "/utils dev --run-tests-all"
    assert router_tools.run_tests.func() == "/utils dev --run-tests-dev"

def test_generate_snapshot_tool():
    assert router_tools.generate_snapshot.func("dev") == "/dev --snapshot-dev"
    assert router_tools.generate_snapshot.func("all", summary="Test Run") == '/dev --snapshot-all --summary "Test Run"'
    assert router_tools.generate_snapshot.func(include_logs=True) == "/dev --snapshot-dev --include-logs"
    assert router_tools.generate_snapshot.func(summarize_modules=True) == "/dev --snapshot-dev --summarize"

def test_list_scripts_tool():
    assert router_tools.list_scripts.func("all") == "/list"
    assert router_tools.list_scripts.func("user") == "/list --type users"
    assert router_tools.list_scripts.func("utils") == "/list --type utilss"

def test_show_help_tool():
    assert router_tools.show_help.func() == "/help"
    assert router_tools.show_help.func("topic") == "/help topic"

def test_update_system_tool():
    assert router_tools.update_system.func() == "/utils update"

def test_get_git_branch_tool():
    assert router_tools.get_git_branch.func() == "/utils git_branch"

def test_add_command_to_category_tool():
    assert router_tools.add_command_to_category.func("ls", "simple") == '/utils command --add "ls" simple'

def test_remove_command_from_category_tool():
    assert router_tools.remove_command_from_category.func("ls") == '/utils command --remove "ls"'

def test_move_command_to_category_tool():
    assert router_tools.move_command_to_category.func("ls", "semi_interactive") == '/utils command --move "ls" semi_interactive'

def test_add_alias_tool():
    assert router_tools.add_alias.func("ll", "ls -l") == '/utils alias --add ll "ls -l"'

def test_remove_alias_tool():
    assert router_tools.remove_alias.func("ll") == '/utils alias --remove ll'

def test_query_knowledge_base_tool():
    assert router_tools.query_knowledge_base.func("what is x") == '/knowledge --name default query "what is x"'
    assert router_tools.query_knowledge_base.func("what is x", kb_name="my_kb") == '/knowledge --name my_kb query "what is x"'

def test_add_file_to_knowledge_base_tool():
    assert router_tools.add_file_to_knowledge_base.func("file.txt") == '/knowledge --name default add-file file.txt'

def test_add_directory_to_knowledge_base_tool():
    assert router_tools.add_directory_to_knowledge_base.func("dir/") == '/knowledge --name default add-dir dir/'

def test_add_url_to_knowledge_base_tool():
    assert router_tools.add_url_to_knowledge_base.func("http://example.com") == '/knowledge --name default add-url http://example.com'
    assert router_tools.add_url_to_knowledge_base.func("http://example.com", recursive=True) == '/knowledge --name default add-url http://example.com --recursive --depth 1'
    assert router_tools.add_url_to_knowledge_base.func("http://example.com", depth=2) == '/knowledge --name default add-url http://example.com --recursive --depth 2'
    assert router_tools.add_url_to_knowledge_base.func("http://example.com", save_cache=True) == '/knowledge --name default add-url http://example.com --save-cache'

def test_query_docs_tool():
    assert router_tools.query_docs.func("how to install") == '/docs --query "how to install" --rag'

def test_get_all_tools_returns_list():
    tools = router_tools.get_all_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Check if a known tool is in the list
    assert router_tools.run_tests in tools

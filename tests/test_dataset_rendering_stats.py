from dataset.rendering_stats import compute_rendering_stats

RICH_PAGE = (
    "<html><head><title>t</title><script>1</script><script>2</script></head>"
    "<body><p>Hello world, this is visible text.</p><div><span>more</span></div></body></html>"
)


def test_counts_nodes_and_scripts():
    stats = compute_rendering_stats(RICH_PAGE)
    assert stats["script_count"] == 2
    assert stats["dom_node_count"] > 0
    assert stats["visible_text_length"] > 0


def test_empty_html_returns_zeros():
    stats = compute_rendering_stats("")
    assert stats == {"dom_node_count": 0, "script_count": 0, "visible_text_length": 0}


def test_thin_spa_shell_has_few_nodes_and_little_text():
    thin = "<html><body><div id='root'></div><script src='bundle.js'></script></body></html>"
    stats = compute_rendering_stats(thin)
    assert stats["visible_text_length"] == 0
    assert stats["script_count"] == 1

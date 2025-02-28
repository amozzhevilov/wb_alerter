from main import get_all_warehouse_from_list


def test_get_all_warehouse_from_list():
    assert (
        get_all_warehouse_from_list(['wh1', 'wh2'], 'prefix', 'postfix') == 'prefix wh1 postfix\nprefix wh2 postfix\n'
    )

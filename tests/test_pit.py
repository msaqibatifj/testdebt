from testdebt.tools.pit import add_pit_plugin, compare, kill_set, parse_kill_matrix
from testdebt.tools.pit import test_method_name as method_of

XML = """<?xml version="1.0"?><mutations>
<mutation detected="true" status="KILLED"><mutatedClass>p.A</mutatedClass><mutatedMethod>f</mutatedMethod>
<lineNumber>3</lineNumber><mutator>M1</mutator><index>0</index>
<killingTests>p.ATest.[engine:junit-jupiter]/[class:p.ATest]/[method:testF()]|p.ATest.[engine:junit-jupiter]/[class:p.ATest]/[method:testG()]</killingTests></mutation>
<mutation detected="true" status="KILLED"><mutatedClass>p.A</mutatedClass><mutatedMethod>g</mutatedMethod>
<lineNumber>7</lineNumber><mutator>M2</mutator><index>0</index><killingTests>p.ATest.testF(p.ATest)</killingTests></mutation>
<mutation detected="false" status="SURVIVED"><mutatedClass>p.A</mutatedClass><mutatedMethod>h</mutatedMethod>
<lineNumber>9</lineNumber><mutator>M3</mutator><index>0</index><killingTests/></mutation>
</mutations>"""


def test_parse_matrix_and_split_union(tmp_path):
    f = tmp_path / "mutations.xml"
    f.write_text(XML)
    mat = parse_kill_matrix(f)
    assert len(mat["testF"]) == 2 and len(mat["testG"]) == 1
    before = kill_set(mat, {"testF"})
    assert not compare(before, kill_set(mat, {"testG"}))["preserved"]            # lost one mutant
    mat["testF_part2"] = {m for m in mat["testF"] if m[1] == "g"}
    assert compare(before, kill_set(mat, {"testG", "testF_part2"}))["preserved"]  # split keeps all


def test_killing_test_name_formats():
    assert method_of("p.T.[engine:junit-jupiter]/[class:p.T]/[method:testX()]") == "testX"
    assert method_of("p.T.testY(p.T)") == "testY"


def test_add_plugin_goes_to_build_plugins_not_management():
    pom = ("<project><build><pluginManagement><plugins><plugin>m</plugin></plugins></pluginManagement>"
           "<plugins><plugin>real</plugin></plugins></build><profiles><profile><build><plugins/></build></profile></profiles></project>")
    out = add_pit_plugin(pom)
    i = out.find("pitest-maven")
    assert out.find("</pluginManagement>") < i < out.find("<plugin>real")
    assert add_pit_plugin(out) == out
    assert "pitest-maven" in add_pit_plugin("<project></project>")

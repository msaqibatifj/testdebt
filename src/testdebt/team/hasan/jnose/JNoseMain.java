// Headless JNose (jnose-core 0.9.0, Java 21): one test file per input line "testPath<TAB>productionPath",
// prints "testPath<TAB>Smell Name<TAB>element" for every smelly element. All smells enabled, maxStatements 30.
import io.github.arieslab.core.Config;
import io.github.arieslab.core.JNoseCore;
import io.github.arieslab.core.testsmelldetector.testsmell.AbstractSmell;
import io.github.arieslab.core.testsmelldetector.testsmell.SmellyElement;
import io.github.arieslab.core.testsmelldetector.testsmell.TestFile;
import io.github.arieslab.core.testsmelldetector.testsmell.TestSmellDetector;

import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Paths;

public class JNoseMain {
    public static void main(String[] args) throws Exception {
        Config cfg = (Config) Proxy.newProxyInstance(Config.class.getClassLoader(), new Class<?>[]{Config.class},
                (p, m, a) -> m.getReturnType() == int.class ? (Object) 30
                        : m.getReturnType() == boolean.class ? (Object) Boolean.TRUE : (Object) "jnose-config");
        new JNoseCore(cfg);                                   // sets VerboseTest.MAX_STATEMENTS
        TestSmellDetector detector = TestSmellDetector.createTestSmellDetector(cfg);
        for (String line : Files.readAllLines(Paths.get(args[0]))) {
            String[] f = line.split("\t", -1);
            TestFile tf = new TestFile("app", f[0], f.length > 1 ? f[1] : "", 0, 0);
            try {
                detector.detectSmells(tf);
            } catch (Exception e) {
                System.out.println(f[0] + "\tERROR\t" + e.toString().replace('\t', ' ').replace('\n', ' '));
                continue;
            }
            for (AbstractSmell s : tf.getTestSmells()) {
                if (s == null) continue;
                for (SmellyElement el : s.getSmellyElements())
                    if (el.getHasSmell()) System.out.println(f[0] + "\t" + s.getSmellName() + "\t" + el.getElementName());
            }
        }
    }
}

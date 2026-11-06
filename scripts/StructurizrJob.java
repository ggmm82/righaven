import java.nio.file.*;
import java.io.*;
import com.structurizr.dsl.StructurizrDslParser;
import com.structurizr.export.AbstractDiagramExporter;
import com.structurizr.export.plantuml.C4PlantUMLExporter;
import com.structurizr.export.mermaid.MermaidDiagramExporter;
import com.structurizr.io.json.JsonWriter;

public class StructurizrJob {
  public static void main(String[] args) throws Exception {
    var parser = new StructurizrDslParser();
    parser.setRestricted(true);
    parser.parse(new File(args[1]));
    var workspace = parser.getWorkspace();
    if (workspace.getModel().getElements().isEmpty() || workspace.getViews().getViews().isEmpty())
      throw new IllegalArgumentException("Workspace must contain a model and at least one view");
    Path output = Path.of(args[2]);
    Files.createDirectories(output);
    try(var writer=Files.newBufferedWriter(output.resolve("workspace.json"))) {
      new JsonWriter(true).write(workspace, writer);
    }
    if (args[0].equals("export")) {
      workspace.getViews().getConfiguration().addProperty(C4PlantUMLExporter.C4PLANTUML_STANDARD_LIBRARY_PROPERTY,"true");
      AbstractDiagramExporter exporter = args[3].equals("mermaid") ? new MermaidDiagramExporter() : new C4PlantUMLExporter();
      int index=0;
      for(var diagram:exporter.export(workspace))
        Files.writeString(output.resolve("view-"+(++index)+"."+diagram.getFileExtension()), diagram.getDefinition());
      if(index==0)throw new IllegalArgumentException("No diagram exported");
    }
    Files.writeString(output.resolve("inspection.json"), "{\"status\":\"passed\",\"elements\":"+workspace.getModel().getElements().size()+",\"relationships\":"+workspace.getModel().getRelationships().size()+",\"views\":"+workspace.getViews().getViews().size()+"}");
  }
}

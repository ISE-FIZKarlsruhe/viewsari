
# Ontology Engineering with XD
For creating the ontology behind the Viewsari KG, our team follows the XD methodology, also reusing and proposing ODPs.
## Requirements Engineering
Requirements engineering is the process of gathering, analyzing, and formalizing requirements for a system (an ontology / KG in our case).
### User Interviews
From user interviews with five stakeholders from the art history domain, we gathered needs and wishes for Viewsari. We collected those
in personas and adjacent user stories.
### User Stories, Personas
We created four personas representing potential stakeholders. They have user scenarios and user requirements, as well as a set of competency questions. These parts are not rigid and can be adjusted with progress in the project.
![viewsari_personas (1189 x 841 mm).png](img/viewsari_personas.png)
## Mapping to ODPs 
In order to increase the interoperability of our ontology, we matched the CQs to existing ODPs (and also created new ones).
We reuse the [Persons](http://ontologydesignpatterns.org/wiki/Submissions:Persons) and [Location](http://ontologydesignpatterns.org/wiki/Submissions:Place) CP from submissions in the [ODP repository](http://ontologydesignpatterns.org/wiki/Main_Page).
Most importantly, we use the [Provenance](http://ontologydesignpatterns.org/wiki/Submissions:Provenance) CP as inspiration for the representation of source evidence for extracted entities and cooccurrences. The solution in the repository does not fully match our use case,
so we adapt it accordingly. We propose a cooccurrence class that has provenance information (e.g. a paragraph) and connects two or more resources.
The examples below showcase what this would look like with data. We also propose a shortcut for authors and their connection to the
cooccurrence.
![odp3.png](img/odp3.png)
![odp2.png](img/odp2.png)
![odp1.png](img/odp1.png)
## Formalization
In the formalization step, we construct a first foundational ontology for Viewsari. This ontology includes the following classes:
![odp1.png](img/classes.png)
For a better view, please open the file in the [directory](https://github.com/ISE-FIZKarlsruhe/viewsari/tree/main/img)

An exemplary view of how cooccurrences are connected to the work level:
![odp1.png](img/cooc_in_context.png)




## References

[1] E. Blomqvist, K. Hammar, V. Presutti, Engineering Ontologies with Patterns - The eXtreme
Design Methodology., in: Ontology Engineering with Ontology Design Patterns - Founda-
tions and Applications, 2016, pp. 23–50. doi:10.3233/978-1-61499-676
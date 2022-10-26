import os
import json
import math
import argparse
import numpy as np
import pandas as pd
import seaborn as sns
import networkx as nx
from wasabi import msg
import matplotlib.pyplot as plt
from pyvis.network import Network


def get_additional_properties(raw_graph, key_to_label):

    filename = "paper_categories.xlsx"
    if os.path.isfile(filename):
        categories = pd.read_excel(filename, sheet_name="main", header=[0])
        categories.set_index("Paper", inplace=True)
    else:
        categories = None

    all_keys = [article["key"] for article in raw_graph["articles"]]

    props = {}
    all_years = []
    all_ids = []
    for key in all_keys:

        # Process categories from xlsx
        if categories is not None:
            cats = categories.loc[key]
            cat_labels = list(cats.index)

            for cat_label in cat_labels:
                prev_props = props.get(cat_label)
                if prev_props is None:
                    prev_props = []

                prev_props.append(cats[cat_label])

                props.update({cat_label: prev_props})

        # Get publication year and ids
        for article in raw_graph["articles"]:
            if article["key"] == key:
                all_years.append(article["year"])
                all_ids.append(key_to_label[article["key"]])
                break

    props.update({"ID": all_ids, "pub_year": all_years})

    additional_properties = pd.DataFrame(props)
    additional_properties.set_index("ID", inplace=True)

    return additional_properties


def create_graph_with_networkx(raw_graph, key_to_label):
    """Create a citation graph with networkx based on a ReViz graph model

    :param raw_graph: graph-model.json from ReViz imported as dict
    :type raw_graph: dict
    :return: networkx citation graph; additional information, that is,
             for now only the publication year per publication
    :rtype: networkx.classes.digraph.DiGraph; pandas DataFrame
    """

    # label_to_key = {v: k for k, v in key_to_label.items()}

    # Define nodes and edges
    all_nodes = [
        key_to_label[article["key"]] for article in raw_graph["articles"]
    ]
    sources = [key_to_label[edge["from"]] for edge in raw_graph["edges"]]
    targets = [key_to_label[edge["to"]] for edge in raw_graph["edges"]]

    df = pd.DataFrame({"From": sources, "To": targets})

    # You may want to define an edge weight according to the number of
    # occurrences of an edge. However, for our citation graph an edge should
    # always occur only once.
    # Additionally, you may want to define other node or edge attributes.
    # However, we do it further below.
    df_graph = df.groupby(["From", "To"]).size().reset_index()
    df_graph.columns = ["From", "To", "Count"]
    print(df_graph)

    # Build graph
    graph = nx.from_pandas_edgelist(
        df_graph, source="From", target="To", create_using=nx.DiGraph()
    )  # edge_attr="Count"

    # Add isolated nodes
    for node in all_nodes:
        graph.add_node(node)

    # Load categories from xlsx
    additional_properties = get_additional_properties(raw_graph, key_to_label)

    # Add additional attributes to node
    for node in graph.nodes:

        # Add labels attribute so that other tools like yED
        # can access the labels after exporting the graph
        # as .graphml file.
        graph.nodes[node]["label"] = node

        # Add additional information about paper
        row = additional_properties.loc[node]
        for prop in list(row.index):
            graph.nodes[node][prop] = row[prop]

    return graph, additional_properties


def visualize_graph_with_networkx(
    graph,
    export_path,
    fig_format,
    additional_properties,
    layout_algorithm="neato",
    node_size=40,
    shift_labels=0,
    fig_width=6.30045,
    aspect_ratio=4 / 3,
    fontsize=5,
    font="Times",
    use_latex=False,
    show_title=False,
    for_powerpoint=False,
):
    """Visualize a citation graph using networkx and matplotlib
     and save the figure to disk.

    :param graph: networkx citation graph
    :type graph: networkx.classes.digraph.DiGraph
    :param additional_properties: additional information, that is, for now
                                  only the publication year per publication
    :type additional_properties: pandas DataFrame
    """

    # Figure width in inches
    # Their are many more layout algorithm, however, GraphViz neato seems to
    # yield decent results.
    #
    # Other GraphViz options are (descriptions from
    # https://stackoverflow.com/questions/21978487/improving-python-networkx-graph-layout):
    #   dot:   "hierarchical" or layered drawings of directed graphs. This is
    #           the default tool to use if edges have directionality.
    #   neato: "spring model'' layouts. This is the default tool to use if the
    #           graph is not too large (about 100 nodes) and you don't know
    #           anything else about it. Neato attempts to minimize a global
    #           energy function, which is equivalent to statistical
    #           multi-dimensional scaling.
    #   fdp:   "spring model'' layouts similar to those of neato, but does
    #           this by reducing forces rather than working with energy.
    #   sfdp:   multiscale version of fdp for the layout of large graphs.
    #   twopi:  radial layouts, after Graham Wills 97. Nodes are placed on
    #           concentric circles depending their distance from a given
    #           root node.
    #   circo:  circular layout, after Six and Tollis 99, Kauffman and
    #           Wiese 02. This is suitable for certain diagrams of multiple
    #           cyclic structures, such as certain telecommunications networks.

    #
    # Other networkx options are:
    #   circular_layout
    #   spring_layout (define k in code below)
    #   kamada_kawai_layout

    # Define colors depending on publication year
    # additional_properties = additional_properties.set_index("ID")

    msg.info("Tip: Export as SVG and run")
    msg.text(
        "  $ inkscape -D --export-latex --export-filename=graph.pdf graph.svg",
        color="cyan",
    )
    msg.text(
        (
            "in order to get PDF which blends in to your LaTeX document "
            "(cf. http://tug.ctan.org/tex-archive/info/svg-inkscape/InkscapePDFLaTeX.pdf)"
        ),
        color="blue",
    )

    if for_powerpoint:
        # Update plot parameters to fit a typical powerpoint slide.
        fig_width = 9.9842519685  # 25.36 cm
        aspect_ratio = fig_width / 5.3228346  # 13.52 cm
        fontsize = 16
        node_size = 60

    plt.rcParams.update(
        {
            "figure.figsize": (
                fig_width,
                fig_width / aspect_ratio,
            ),
            "font.size": fontsize,
            "axes.labelsize": fontsize,
            "legend.fontsize": fontsize,
            "font.family": font,
            "text.usetex": use_latex,
            "svg.fonttype": "none",
            "pgf.rcfonts": False,
            "text.latex.preamble": (
                r"\usepackage{lmodern}"
                # add additional packages here
            ),
        }
    )

    additional_properties = additional_properties.reindex(graph.nodes())

    for category in list(additional_properties.columns):

        category_values = set(additional_properties[category])

        # Sort if possible
        try:
            num_category_values = [int(v) for v in category_values]
            category_values = sorted(category_values)
            is_categorical_variable = False
        except:
            is_categorical_variable = True

        # Init plot.
        fig, ax = plt.subplots(constrained_layout=True)

        # Add a title.
        if show_title:
            font = {"color": "k", "fontweight": "bold", "fontsize": 20}
            ax.set_title("Citation Graph", font)

        # Get the postion of the nodes.
        if layout_algorithm in [
            "dot",
            "neato",
            "fdp",
            "sfdp",
            "twopi",
            "circo",
        ]:
            pos = nx.nx_agraph.graphviz_layout(
                graph, prog=layout_algorithm
            )  # dot, neato, fdp, sfdp, twopi, circo
        elif layout_algorithm == "circular_layout":
            pos = nx.circular_layout(graph)
        elif layout_algorithm == "spring_layout":
            pos = nx.spring_layout(graph, k=10 / math.sqrt(graph.order()))
        elif layout_algorithm == "kamada_kawai_layout":
            pos = nx.kamada_kawai_layout(graph)

        # Get the color map.
        if is_categorical_variable:
            # Define colors for categorical variables.
            if len(category_values) <= 10:
                # This map has only ten different colors defined.
                palette = "tab10"
            else:
                # For arbitrary number of categories.
                palette = "hls"

            colors = sns.color_palette(palette, len(category_values))

        else:
            # Define colors for continues variables.
            palette = sns.color_palette(
                "viridis_r",
                max(num_category_values) - min(num_category_values) + 1,
            )
            colors = []
            for i, v in enumerate(
                range(min(num_category_values), max(num_category_values) + 1)
            ):
                if v in num_category_values:
                    colors.append(palette[i])

        # Add nodes of current category.
        for color, category_value in zip(colors, category_values):
            nodes_of_category = additional_properties.index[
                additional_properties[category] == category_value
            ].tolist()
            nx.draw_networkx_nodes(
                graph,
                pos=pos,
                nodelist=nodes_of_category,
                node_size=node_size,
                node_color=np.array([color]),
                label=category_value,
            )

        # Shift labels sideways.
        if shift_labels > 0:
            pos_shift = {}
            for node, coords in pos.items():
                pos_shift[node] = (coords[0] + shift_labels, coords[1])
            pos = pos_shift

        # Add edges.
        nx.draw_networkx_edges(graph, pos=pos, node_size=node_size)

        # Add node labels.
        nx.draw_networkx_labels(
            graph, pos, font_size=fontsize, font_family="sans-serif"
        )

        # Add a legend.
        if category != "pub_year":
            # No legend for publication year since
            # it is likely too large for all years
            # and the year can be read from the
            # labels anyways.
            plt.legend(scatterpoints=1)

        # No frame around the figure.
        ax.axis("off")

        # Export figure.
        plt.savefig(
            export_path
            + "_"
            + category.lower().replace(" ", "_")
            + "_colored."
            + fig_format
        )

        # For experimenting within jupyter notebooks you can define SVG
        # as preferred format want to define:
        # %config InlineBackend.figure_formats = ['svg']

        # Show graph with node color according to publication year
        if category == "pub_year":
            plt.show()

        plt.close(fig)


def create_graph_with_pyvis(raw_graph):
    """Create a citation graph with pyvis based on a ReViz graph model

    :param raw_graph: graph-model.json from ReViz imported as dict
    :type raw_graph: dict
    :return: pyvis citation graph
    :rtype: pyvis.network.Network
    """

    # Define nodes and edges
    sources = [edge["from"] for edge in raw_graph["edges"]]
    targets = [edge["to"] for edge in raw_graph["edges"]]

    # Define edges
    edge_data = zip(sources, targets)

    # Define colors depending on publication year
    years = sorted(set(raw_graph["years"]))
    cmap = plt.cm.get_cmap("plasma", len(years))

    color_map = []
    for i, color in enumerate(cmap.colors):
        color_map.append([int(c * 255) for c in color[0:3]])
        color_map[i].append(color[3])

    colors = {
        year: "rgba" + str(tuple(color))
        for (year, color) in zip(years, color_map)
    }

    # Init network
    graph = Network(height="750px", width="65%")
    # You may want to specify additional properties like
    # bgcolor='#222222', font_color='white' or, directed=True

    # Set the network layout
    graph.barnes_hut()

    # Build network
    for e in edge_data:
        src = e[0]
        dst = e[1]
        w = 1

        years = raw_graph["year_arts"].keys()
        year = lambda x: int(
            [year for year in years if x in raw_graph["year_arts"][year]][0]
        )
        year_src = year(src)
        year_dst = year(dst)

        expand_years = False
        if expand_years:
            distance = 0.05
            all_levels = [node["level"] for node in graph.nodes]
            while year_src in all_levels:
                year_src += distance

            all_levels.append(year_src)
            while year_dst in all_levels:
                year_dst += distance

        graph.add_node(
            src, src, title=src, level=year_src, color=colors[year_src]
        )  # , physics=False)
        graph.add_node(
            dst, dst, title=dst, level=year_dst, color=colors[year_dst]
        )  # , physics=False)
        graph.add_edge(src, dst, value=w, arrowStrikethrough=False)

    return graph


def visualize_graph_with_pyvis(graph):
    """Visualize a citation graph using pyvis and matplotlib.
    The visualization is rendered in your browser. A browser
    window should open automatically.

    :param graph: pyvis citation graph
    :type graph: pyvis.network.Network
    """

    graph.set_edge_smooth("cubicBezier")

    # Which filters to show?
    filter_mode = "all_filters"
    if filter_mode == "all_filters":
        graph.show_buttons()
    elif filter_mode == "specific_filters":
        graph.show_buttons(filter_=["edges", "layout", "physics"])
    elif filter_mode == "preset_with_options":
        # With this mode no filter will be visible, but the options
        # are predefined using the string below
        graph.set_options(
            """
        var options = {
        "edges": {
            "arrows": {
            "to": {
                "enabled": true,
                "scaleFactor": 0.7
            }
            },
            "color": {
                "inherit": true,
                "opacity": 0.65
            },
            "font": {
             "strokeWidth": 1
            },
            "scaling": {
                "min": 4,
                "max": 11
            },
            "smooth": {
                "type": "cubicBezier",
                "forceDirection": "none"
            }
        },
        "layout": {
            "hierarchical": {
                "enabled": true,
                "direction": "LR",
                "sortMethod": "directed"
            }
        }
        """
        )

    graph.show("citation_graph.html")


def draw_graph(
    graph_model_file,
    json_bib_file="prepared_library.json",
    render_in_browser=False,
    save_fig=True,
    fig_format="svg",
    export=True,
    export_format="graphml",
    export_filename="citation_graph",
    fontsize=5,
    node_size=40,
    use_latex=False,
    fig_width=6.30045,
    aspect_ratio=4 / 3,
):

    # Get graph model
    with open(graph_model_file, encoding="utf-8") as f:
        raw_graph = json.load(f)

    # Get article information
    with open(json_bib_file, "r") as file:  # encoding='utf8'
        bib = json.load(file)

    articles = bib["final selection articles"]
    key_to_label = {}
    for article in articles:
        key_to_label.update({article["bibtex_key"]: article["label"]})

    if save_fig or export:
        # Create graph with networkx
        graph, additional_properties = create_graph_with_networkx(
            raw_graph, key_to_label
        )

        graph_dir = os.path.dirname(graph_model_file)
        export_path = os.path.join(graph_dir, export_filename)

        if save_fig:
            # Visualize graph with networkx
            visualize_graph_with_networkx(
                graph,
                export_path,
                fig_format,
                additional_properties,
                fontsize=fontsize,
                node_size=node_size,
                use_latex=use_latex,
                fig_width=fig_width,
                aspect_ratio=aspect_ratio,
            )

        if export:
            # Export graph for further use in other tools
            if export_format == "graphml":
                nx.write_graphml(graph, export_path + ".graphml")
            elif export_format == "gexf":
                nx.write_gexf(graph, export_path + ".gexf")
            else:
                raise ValueError(
                    (
                        "Unknown export file format. Use graphml "
                        "or gexf or extend the programm code."
                    )
                )

    if render_in_browser:

        # TODO: It is also possible to create a Pyvis graph from a
        # networkx graph instead of creating it from scratch. With this
        # the networkx graph can be rendered in the browser using Pyvis.

        # Create graph with Pyvis
        graph = create_graph_with_pyvis(raw_graph)

        # Render graph in browser
        visualize_graph_with_pyvis(graph)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--graph_model_file",
        help="""path to graph-model JSON file
    according to ReViz""",
        type=str,
        default="./augmented_graph/graph-model.json",
    )

    parser.add_argument(
        "--json_bib_file",
        help="Path of the preprocessed BibTeX file, which is a JSON file.",
        default="prepared_library.json",
    )

    parser.add_argument(
        "--render_in_browser",
        help="""Render the graph in your browser.""",
        action="store_true",
    )

    parser.add_argument(
        "--save_fig", help="""Save graph as figure.""", action="store_true"
    )

    parser.add_argument(
        "--fig_format", help="File format of figure", type=str, default="svg"
    )

    parser.add_argument(
        "--export",
        help="""Export the graph definition to a graphml or similar filetype.""",
        action="store_true",
    )
    parser.add_argument(
        "--export_format",
        help="Graph file format",
        type=str,
        default="graphml",
    )

    parser.add_argument(
        "--export_filename",
        help="Export filename",
        type=str,
        default="citation_graph",
    )

    parser.add_argument(
        "--fontsize",
        help="Fontsize of the node labels of the graph.",
        type=int,
        default=12,
    )

    parser.add_argument(
        "--nodesize",
        help="Size of the nodes in the graph.",
        type=int,
        default=60,
    )
    parser.add_argument(
        "--use_latex",
        help="Whether to render text with TeX or not.",
        type=bool,
        default=False,
    )

    parser.add_argument(
        "--fig_width",
        help="The width of the figure in inches.",
        type=int,
        default=6.3,
    )

    parser.add_argument(
        "--aspect_ratio",
        help="The aspect ratio of the figure.",
        type=int,
        default=4 / 3,
    )

    args = parser.parse_args()

    draw_graph(
        args.graph_model_file,
        json_bib_file=args.json_bib_file,
        render_in_browser=args.render_in_browser,
        save_fig=args.save_fig,
        fig_format=args.fig_format,
        export=args.export,
        export_format=args.export_format,
        export_filename=args.export_filename,
        fontsize=args.fontsize,
        node_size=args.nodesize,
        use_latex=args.use_latex,
        fig_width=args.fig_width,
        aspect_ratio=args.aspect_ratio,
    )

# Haywire Visiongraph Library

This is the Visiongraph library demonstrating the Haywire library system capabilities.

## Features

- **Types**: Example data types with serialization support
- **Nodes**: Nodes for data processing and display
- **Widgets**: UI widgets for node configuration
- **Renderers**: Node rendering customization
- **Adapters**: Integration with external systems

## Installation

### Development (Editable Install)

For development with hot-reload support:

```bash
cd libraries/visiongraph
uv pip install -e .
```

### Production

```bash
uv pip install haybale-visiongraph
```

## Usage

Once installed, the library is automatically discovered by Haywire through entry points.

The library provides:
- Display nodes for visualization
- Dynamic nodes for runtime node creation
- Example custom data types
- Custom UI widgets and renderers

## Structure

```
📁 haybale-visiongraph/                    # Git repo name / unique pip package name
├── pyproject.toml
│   [project]
│   name = "haybale-visiongraph"          # pip install haybale-visiongraph
│   
│   [project.entry-points."haywire.libraries"]
│   visiongraph = "haybale_visiongraph:Library"      # ID matches module
│
└── 📁 haybale_visiongraph/                        # import haybale_visiongraph
    ├── __init__.py
    │   @library(
    │       id='VISIONGRAPH',              # Matches entry point
    │       label='Visiongraph',
    │   )
    │   class Library(BaseLibrary): ...
    ├── nodes/               # Custom nodes
    ├── types/               # Custom data types (if any)
    ├── widgets/             # Custom UI widgets
    ├── renderers/           # Custom node renderers
    └── adapters/            # External system adapters
```

## Development

After making changes to the library code:

1. **With editable install**: Changes are immediately reflected (after hot-reload)
2. **Without editable install**: Reinstall the package

## Entry Point

This library is discoverable via the `haywire.libraries` entry point:

```toml
[project.entry-points."haywire.libraries"]
visiongraph = "haybale_visiongraph:Library"
```

## Dependencies

- haywire-core >= 1.0.0

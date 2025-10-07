#!/usr/bin/env python3

import os
import yaml
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import shutil


def load_yaml_data(filepath):
    """Load YAML data from file."""
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def strftime_filter(date_str, format_str='%b %d, %Y'):
    """Custom Jinja2 filter to format date strings."""
    if isinstance(date_str, str):
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime(format_str)
    return date_str


def main():
    # Set up directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    templates_dir = os.path.join(script_dir, 'templates')
    static_dir = os.path.join(script_dir, 'static')
    output_dir = os.path.join(script_dir, 'output')

    # Clean and create output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Copy static files to output
    if os.path.exists(static_dir):
        static_output = os.path.join(output_dir, 'static')
        shutil.copytree(static_dir, static_output)

    # Load data
    print("Loading data...")
    site_config = load_yaml_data(os.path.join(data_dir, 'site_config.yaml'))
    episodes_data = load_yaml_data(os.path.join(data_dir, 'episodes.yaml'))
    guests_data = load_yaml_data(os.path.join(data_dir, 'guests.yaml'))

    # Set up Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Add custom filters
    env.filters['strftime'] = strftime_filter

    # Prepare template data
    template_data = {
        **site_config,
        # 'episodes': episodes_data.get('episodes'),
        # 'guests': guests_data.get('guests'),
        # 'build_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Generate index.html
    print("Generating index.html...")
    template = env.get_template('index.html')
    output_html = template.render(**template_data)

    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(output_html)

    print(f"✅ Static site generated successfully!")
    print(f"📁 Output directory: {output_dir}")
    print(f"🌐 Open {os.path.join(output_dir, 'index.html')} in your browser")


if __name__ == "__main__":
    main()
"""Command-line helper to process an area via the satellite pipeline."""
import argparse

from ..satellite import satellite_inference_pipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("area", help="Area identifier")
    parser.add_argument("model", help="Path to saved trajectory model")
    args = parser.parse_args()

    satellite_inference_pipeline.run(args.area, args.model)


if __name__ == "__main__":
    main()

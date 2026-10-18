"""Scaffold a brand from its website: config/<slug>.yml and a Stage 5 folder.

  python new_brand.py <slug> "<Company name>" <website url>

The config is created with TODOs. Claude (or you) fills them from the website and public sources,
you confirm them, and only then does run_brand.sh start.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    slug, company, url = sys.argv[1].lower(), sys.argv[2], sys.argv[3]
    dest = os.path.join(ROOT, "config", "%s.yml" % slug)
    if os.path.exists(dest):
        sys.exit("config/%s.yml already exists" % slug)
    s = open(os.path.join(ROOT, "config", "_template.yml")).read()
    s = s.replace("TODO_COMPANY", company).replace("TODO_URL", url)
    open(dest, "w").write(s)
    os.makedirs(os.path.join(ROOT, "stage5", slug), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "stage5", "_template_build.py"), os.path.join(ROOT, "stage5", slug, "build_template.py"))
    print("created config/%s.yml (%d TODOs to resolve) and stage5/%s/" % (slug, s.count("TODO"), slug))


if __name__ == "__main__":
    main()

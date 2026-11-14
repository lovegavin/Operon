import type {Catalog} from './types';

/** An in-flight catalog read may not overwrite a later install/publish result. */
export class CatalogUpdates {
  private revision = 0;
  checkpoint() {return this.revision;}
  force(catalog: Catalog, update: (catalog: Catalog) => void) {
    this.revision++;
    update(catalog);
  }

  apply(catalog: Catalog, update: (catalog: Catalog) => void, expected = this.revision): boolean {
    if (expected !== this.revision) return false;
    this.revision++;
    update(catalog);
    return true;
  }
}

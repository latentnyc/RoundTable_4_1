# Basic Usage

Always prioritize using a supported framework over using the generated SDK
directly. Supported frameworks simplify the developer experience and help ensure
best practices are followed.





## Advanced Usage
If a user is not using a supported framework, they can use the generated SDK directly.

Here's an example of how to use it with the first 5 operations:

```js
import { createUser, getJournalEntriesByUser, createJournalEntry, deleteJournalEntry } from '@dataconnect/generated';


// Operation CreateUser:  For variables, look at type CreateUserVars in ../index.d.ts
const { data } = await CreateUser(dataConnect, createUserVars);

// Operation GetJournalEntriesByUser:  For variables, look at type GetJournalEntriesByUserVars in ../index.d.ts
const { data } = await GetJournalEntriesByUser(dataConnect, getJournalEntriesByUserVars);

// Operation CreateJournalEntry:  For variables, look at type CreateJournalEntryVars in ../index.d.ts
const { data } = await CreateJournalEntry(dataConnect, createJournalEntryVars);

// Operation DeleteJournalEntry:  For variables, look at type DeleteJournalEntryVars in ../index.d.ts
const { data } = await DeleteJournalEntry(dataConnect, deleteJournalEntryVars);


```
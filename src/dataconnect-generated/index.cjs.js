const { queryRef, executeQuery, mutationRef, executeMutation, validateArgs } = require('firebase/data-connect');

const connectorConfig = {
  connector: 'example',
  service: 'roundtable41',
  location: 'us-east4'
};
exports.connectorConfig = connectorConfig;

const createUserRef = (dcOrVars, vars) => {
  const { dc: dcInstance, vars: inputVars} = validateArgs(connectorConfig, dcOrVars, vars, true);
  dcInstance._useGeneratedSdk();
  return mutationRef(dcInstance, 'CreateUser', inputVars);
}
createUserRef.operationName = 'CreateUser';
exports.createUserRef = createUserRef;

exports.createUser = function createUser(dcOrVars, vars) {
  return executeMutation(createUserRef(dcOrVars, vars));
};

const getJournalEntriesByUserRef = (dcOrVars, vars) => {
  const { dc: dcInstance, vars: inputVars} = validateArgs(connectorConfig, dcOrVars, vars, true);
  dcInstance._useGeneratedSdk();
  return queryRef(dcInstance, 'GetJournalEntriesByUser', inputVars);
}
getJournalEntriesByUserRef.operationName = 'GetJournalEntriesByUser';
exports.getJournalEntriesByUserRef = getJournalEntriesByUserRef;

exports.getJournalEntriesByUser = function getJournalEntriesByUser(dcOrVars, vars) {
  return executeQuery(getJournalEntriesByUserRef(dcOrVars, vars));
};

const createJournalEntryRef = (dcOrVars, vars) => {
  const { dc: dcInstance, vars: inputVars} = validateArgs(connectorConfig, dcOrVars, vars, true);
  dcInstance._useGeneratedSdk();
  return mutationRef(dcInstance, 'CreateJournalEntry', inputVars);
}
createJournalEntryRef.operationName = 'CreateJournalEntry';
exports.createJournalEntryRef = createJournalEntryRef;

exports.createJournalEntry = function createJournalEntry(dcOrVars, vars) {
  return executeMutation(createJournalEntryRef(dcOrVars, vars));
};

const deleteJournalEntryRef = (dcOrVars, vars) => {
  const { dc: dcInstance, vars: inputVars} = validateArgs(connectorConfig, dcOrVars, vars, true);
  dcInstance._useGeneratedSdk();
  return mutationRef(dcInstance, 'DeleteJournalEntry', inputVars);
}
deleteJournalEntryRef.operationName = 'DeleteJournalEntry';
exports.deleteJournalEntryRef = deleteJournalEntryRef;

exports.deleteJournalEntry = function deleteJournalEntry(dcOrVars, vars) {
  return executeMutation(deleteJournalEntryRef(dcOrVars, vars));
};

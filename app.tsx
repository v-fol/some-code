import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import "./css/index.css";

import { ISearchResults } from "./types/types";

import SearchPage from "./pages/SearchPage";
import SearchResultsPage from "./pages/SearchResultsPage";
import CompanyDescriprionPage from "./pages/CompanyDescriprionPage";

const App = () => {
  const [searchResults, setSearchResults] = useState<ISearchResults[]>([]);

  const updateSearchResults = (results: ISearchResults[]): void => {
    setSearchResults(results);
  };

  return (
    <>
      <Routes>
        <Route
          path="/company"
          element={
            <CompanyDescriprionPage updateSearchResults={updateSearchResults} />
          }
        />
        <Route
          path="/search"
          element={
            <SearchResultsPage
              searchResults={searchResults}
              updateSearchResults={updateSearchResults}
            />
          }
        />
        <Route
          path="/"
          element={<SearchPage updateSearchResults={updateSearchResults} />}
        />
      </Routes>
    </>
  );
};

export default App;
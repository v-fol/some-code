import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";

import {
  ISearchPredictions,
  ISearchText,
  ISearchResults,
} from "../../types/types";

import removeLastWord from "../../utils";
import ArrowSvg from "../../assets/svg/ArrowSvg";

import {
  rapidApiAxiosInstance,
  azureSearchAxiosinstance,
} from "../../axiosApi";

const SearchBar = ({ updateSearchResults }) => {
  let navigate = useNavigate();

  const [searchText, setSearchText] = useState<ISearchText>({
    text: "",
  });
  const [searchPredictions, setSearchPredictions] = useState<ISearchPredictions[]>([]);

  const searchAutocomplete = async (text: string) => {
    await rapidApiAxiosInstance
      .post("/completion/complete", {
        text: text,
      })
      .bind(
        (response: {
          data: { predictions: React.SetStateAction<ISearchPredictions[]> };
        }) => setSearchPredictions(response.data.predictions)
      );
  };

  const search = async (query: string) => {
    await azureSearchAxiosinstance
      .get("/api/v2/search", {
        q: query,
      })
      .bind(
        (response: {
          data: { companiesList: React.SetStateAction<ISearchResults[]> };
        }) => updateSearchResults(response.data.companiesList)
      )
      .bind(() => setSearchPredictions([]));
  };

  return (
    <div className="relative w-full text-gray-600 drop-shadow-xl px-2">
      <div className="border-2 bg-white p-1 border-gray-400 rounded-3xl ">
        <div className="bg-white h-10 flex items-center rounded-xl p-2">
          <input
            value={searchText.text}
            onKeyPress={(e) => {
              if (e.key === "Enter") {
                search(searchText.text);
                navigate(`/search?q=${searchText.text}`);
              }
            }}
            onChange={(e) => (
              setSearchText({ text: e.target.value }),
              searchAutocomplete(e.target.value)
            )}
            autoComplete="on"
            type="search"
            name="search"
            placeholder="Search"
            className="pl-3 w-full rounded-l-full h-8 bg-opacity-0 focus:outline-none"
          />
          <Link
            to={`/search?q=${searchText.text}`}
            onClick={() => search(searchText.text)}
            className="ml-4 mr-3"
          >
            <ArrowSvg />
          </Link>
        </div>
        {searchPredictions.length > 0 && (
          <div className="h-[3px] mb-1 mx-4 rounded-full bg-gray-300"></div>
        )}
        {searchPredictions.map((textSuggestion, index) => (
          <p
            onClick={() => {
              setSearchText({
                text: `${removeLastWord(searchText.text)}${
                  textSuggestion.text
                } `,
              });
              searchAutocomplete(
                `${removeLastWord(searchText.text)}${textSuggestion.text} `
              );
            }}
            key={index}
            className="mx-4 px-1 rounded-lg py-1 cursor-pointer hover:bg-gray-300"
          >
            {removeLastWord(searchText.text)}
            <span className="font-bold">{textSuggestion.text}</span>
          </p>
        ))}
      </div>
    </div>
  );
};

export default SearchBar;
